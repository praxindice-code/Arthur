-- BayesGuard starter for Roblox's Platformer/Obby template.
-- Put this Script in ServerScriptService. It never kicks or bans anyone.
-- The template's dash and long jump target about 60 studs/second, so the
-- limits below intentionally look only for much larger jumps in position.

local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local CollectionService = game:GetService("CollectionService")

local SAMPLE_SECONDS = 0.5
local SPAWN_GRACE_SECONDS = 3
local MAX_SAMPLE_GAP_SECONDS = 1.5
local MAX_HORIZONTAL_STUDS_PER_SECOND = 125
local MAX_UPWARD_STUDS_PER_SECOND = 150
local WINDOW_SECONDS = 12
local FLAGS_FOR_REVIEW = 3
local REVIEW_COOLDOWN_SECONDS = 20

type PlayerState = {
    character: Model?,
    lastPosition: Vector3?,
    lastTime: number?,
    graceUntil: number,
    flags: {number},
    lastReview: number,
}

local states: {[Player]: PlayerState} = {}

local function isOnMovingPlatform(character: Model, root: BasePart): boolean
    local params = RaycastParams.new()
    params.FilterType = Enum.RaycastFilterType.Exclude
    params.FilterDescendantsInstances = { character }
    local result = workspace:Raycast(root.Position, Vector3.new(0, -7, 0), params)
    if not result then
        return false
    end
    local part: Instance? = result.Instance
    while part and part ~= workspace do
        if CollectionService:HasTag(part, "MovingPlatform") then
            return true
        end
        part = part.Parent
    end
    return false
end

local function sample(player: Player, now: number)
    local state = states[player]
    if not state then
        return
    end

    local character = player.Character
    local humanoid = character and character:FindFirstChildOfClass("Humanoid")
    local root = character and character:FindFirstChild("HumanoidRootPart")
    if not character or not humanoid or not root or not root:IsA("BasePart") then
        state.lastPosition = nil
        state.lastTime = nil
        return
    end

    if state.character ~= character then
        state.character = character
        state.graceUntil = now + SPAWN_GRACE_SECONDS
        state.lastPosition = nil
        state.lastTime = nil
        state.flags = {}
    end

    local position = root.Position
    local previous = state.lastPosition
    local previousTime = state.lastTime
    state.lastPosition = position
    state.lastTime = now
    if not previous or not previousTime then
        return
    end

    local dt = now - previousTime
    if now < state.graceUntil or dt <= 0 or dt > MAX_SAMPLE_GAP_SECONDS
        or humanoid.Health <= 0 or humanoid.Sit then
        return
    end

    -- A legitimate server teleport can set this attribute before moving a player.
    local teleportGraceUntil = character:GetAttribute("BayesGuardMovementGraceUntil")
    if typeof(teleportGraceUntil) == "number" and now < teleportGraceUntil then
        return
    end
    if isOnMovingPlatform(character, root) then
        return
    end

    local delta = position - previous
    local horizontalSpeed = Vector3.new(delta.X, 0, delta.Z).Magnitude / dt
    -- Do not treat an ordinary long fall as a cheat signal.
    local upwardSpeed = delta.Y / dt
    if horizontalSpeed <= MAX_HORIZONTAL_STUDS_PER_SECOND
        and upwardSpeed <= MAX_UPWARD_STUDS_PER_SECOND then
        return
    end

    table.insert(state.flags, now)
    while #state.flags > 0 and now - state.flags[1] > WINDOW_SECONDS do
        table.remove(state.flags, 1)
    end
    if #state.flags >= FLAGS_FOR_REVIEW and now - state.lastReview >= REVIEW_COOLDOWN_SECONDS then
        state.lastReview = now
        warn(string.format(
            "[BayesGuard review only] %s (%d): %d large movement samples in %.0fs; last horizontal=%.1f, upward=%.1f studs/s",
            player.Name, player.UserId, #state.flags, WINDOW_SECONDS,
            horizontalSpeed, upwardSpeed
        ))
    end
end

Players.PlayerAdded:Connect(function(player)
    states[player] = {
        character = nil,
        lastPosition = nil,
        lastTime = nil,
        graceUntil = 0,
        flags = {},
        lastReview = -math.huge,
    }
    print("[BayesGuard] Observing movement for", player.Name, "(review only)")
end)

Players.PlayerRemoving:Connect(function(player)
    states[player] = nil
end)

local elapsed = 0
RunService.Heartbeat:Connect(function(dt)
    elapsed += dt
    if elapsed < SAMPLE_SECONDS then
        return
    end
    elapsed = 0
    local now = time()
    for _, player in Players:GetPlayers() do
        sample(player, now)
    end
end)

print("[BayesGuard] Place1 obby observer ready; no enforcement enabled")
