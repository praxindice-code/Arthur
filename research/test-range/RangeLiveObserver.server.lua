-- The real-player adapter uses exactly the same detector as the dummy tests.
-- Put beside MovementDetector in ServerScriptService. Review only.
local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local CollectionService = game:GetService("CollectionService")
local MovementDetector = require(script.Parent.MovementDetector)

local detector = MovementDetector.new()
local playerState = {}
local reviewSignal = Instance.new("BindableEvent")
reviewSignal.Name = "BayesGuardReviewSignal"
reviewSignal.Parent = script.Parent

local function onMovingPlatform(character, root)
    local params = RaycastParams.new()
    params.FilterType = Enum.RaycastFilterType.Exclude
    params.FilterDescendantsInstances = { character }
    local hit = workspace:Raycast(root.Position, Vector3.new(0, -7, 0), params)
    if not hit then return false end
    local item = hit.Instance
    while item and item ~= workspace do
        if CollectionService:HasTag(item, "MovingPlatform") then
            return true
        end
        item = item.Parent
    end
    return false
end

local function sample(player, now)
    local state = playerState[player]
    if not state then return end
    local character = player.Character
    local humanoid = character and character:FindFirstChildOfClass("Humanoid")
    local root = character and character:FindFirstChild("HumanoidRootPart")
    if not character or not humanoid or not root or not root:IsA("BasePart") then
        detector:reset(player)
        return
    end
    if state.character ~= character then
        detector:reset(player)
        state.character = character
        state.graceUntil = now + 3
    end
    local teleportGrace = character:GetAttribute("BayesGuardMovementGraceUntil")
    local ignore = now < state.graceUntil
        or humanoid.Health <= 0 or humanoid.Sit
        or (typeof(teleportGrace) == "number" and now < teleportGrace)
        or onMovingPlatform(character, root)
    local result = detector:observe(player, now, root.Position, { ignore = ignore })
    if result.review then
        reviewSignal:Fire(player, result)
        warn(string.format(
            "[ArthurAI review only] %s (%d): %d large moves; horizontal=%.1f, upward=%.1f studs/s",
            player.Name, player.UserId, result.flagCount,
            result.horizontal, result.upward
        ))
    end
end

Players.PlayerAdded:Connect(function(player)
    playerState[player] = { character = nil, graceUntil = 0 }
end)
Players.PlayerRemoving:Connect(function(player)
    playerState[player] = nil
    detector:reset(player)
end)
for _, player in Players:GetPlayers() do
    playerState[player] = { character = nil, graceUntil = 0 }
end

local elapsed = 0
RunService.Heartbeat:Connect(function(dt)
    elapsed += dt
    if elapsed < 0.5 then return end
    elapsed = 0
    local now = time()
    for _, player in Players:GetPlayers() do
        sample(player, now)
    end
end)
print("[ArthurAI] Shared live movement observer ready; review only")
