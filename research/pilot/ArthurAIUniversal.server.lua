-- ArthurAI universal Roblox pilot, version 3.
-- Put this Script in ServerScriptService. It observes; it never kicks, bans,
-- changes movement, reads RemoteEvent arguments, or sends data to a website.
-- Explicitly set this Script's attribute ArthurAIPilotEnabled = true to run it.
local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local HttpService = game:GetService("HttpService")

if script:GetAttribute("ArthurAIPilotEnabled") ~= true then
    print("[ArthurAI pilot] Disabled. Set Script attribute ArthurAIPilotEnabled=true after pilot approval.")
    return
end

local SAMPLE_SECONDS = 0.5
local WINDOW_SECONDS = 10
local MAX_WINDOWS_PER_SERVER = 2000
local MAX_WATCHED_REMOTES = 5000
local MAX_REMOTES_PER_WINDOW = 10000
local MOVEMENT_CONTEXTS = {"grounded", "airborne", "ragdoll", "vehicle"}
local sessions = {}
local watchedRemotes = {}
local watchedRemoteCount = 0
local emitted = 0
local limitWarned = false

-- Server-only subscribers can map an anonymous session to a Player for review.
-- This event is not replicated, and no player identity enters shared telemetry.
local windowEvent = Instance.new("BindableEvent")
windowEvent.Name = "ArthurAIWindow"
windowEvent.Parent = script

local function newWindow(state, now)
    state.windowStart = now
    state.windowIndex += 1
    state.samples = 0
    state.maxHorizontal = 0
    state.maxUpward = 0
    state.remoteCount = 0
    state.ignoredMovement = 0
    state.remoteRejectCount = 0
    state.rewardMismatchCount = 0
    state.invalidHitCount = 0
    state.approvedMovementCount = 0
    state.nonfiniteMovementCount = 0
    state.movementContexts = {}
    for _, name in MOVEMENT_CONTEXTS do
        state.movementContexts[name] = {
            samples = 0, max_horizontal = 0, max_upward = 0,
        }
    end
end

local function emit(player, state)
    if emitted >= MAX_WINDOWS_PER_SERVER then
        if not limitWarned then
            limitWarned = true
            warn("[ArthurAI pilot] Output limit reached; this is not a durable live telemetry service")
        end
        return
    end
    emitted += 1
    -- No player name, UserId, IP, chat, RemoteEvent arguments, or raw positions.
    local row = {
        schema = 3,
        game_id = tostring(game.GameId),
        session_id = state.id,
        window = state.windowIndex,
        started_at = state.startedAt,
        samples = state.samples,
        max_horizontal = math.floor(state.maxHorizontal * 10 + 0.5) / 10,
        max_upward = math.floor(state.maxUpward * 10 + 0.5) / 10,
        remote_count = state.remoteCount,
        ignored_movement = state.ignoredMovement,
        remote_reject_count = state.remoteRejectCount,
        reward_mismatch_count = state.rewardMismatchCount,
        invalid_hit_count = state.invalidHitCount,
        approved_movement_count = state.approvedMovementCount,
        nonfinite_movement_count = state.nonfiniteMovementCount,
        movement_contexts = state.movementContexts,
    }
    print("ARTHURAI_PILOT_V3 " .. HttpService:JSONEncode(row))
    windowEvent:Fire(player, row)
    if emitted == MAX_WINDOWS_PER_SERVER and not limitWarned then
        limitWarned = true
        warn("[ArthurAI pilot] Output limit reached; sampling paused for this server")
    end
end

-- The optional module is only callable from other server Scripts. These
-- categories represent outcomes of the game's own validation, not client claims.
local eventModule = script.Parent:FindFirstChild("ArthurAIEvents")
if eventModule and eventModule:IsA("ModuleScript") then
    local Events = require(eventModule)
    Events.bind(function(player, kind, detail)
        if emitted >= MAX_WINDOWS_PER_SERVER then return end
        local state = sessions[player]
        if not state then return end
        if kind == "remote_reject" then
            state.remoteRejectCount = math.min(state.remoteRejectCount + 1, 10000)
        elseif kind == "reward_mismatch" then
            state.rewardMismatchCount = math.min(state.rewardMismatchCount + 1, 10000)
        elseif kind == "invalid_hit" then
            state.invalidHitCount = math.min(state.invalidHitCount + 1, 10000)
        elseif kind == "approved_movement" then
            state.approvedMovementCount = math.min(state.approvedMovementCount + 1, 10000)
            state.approvedUntil = math.max(state.approvedUntil or 0, time() + detail)
        elseif kind == "movement_context" then
            state.contextName = detail.name
            state.contextUntil = time() + detail.seconds
        end
    end)
end

local function attachPlayer(player)
    local now = time()
    local state = {
        id = HttpService:GenerateGUID(false),
        startedAt = os.time(),
        character = nil,
        previousPosition = nil,
        previousTime = nil,
        previousContext = nil,
        graceUntil = now + 3,
        approvedUntil = 0,
        contextName = nil,
        contextUntil = 0,
        windowIndex = -1,
    }
    sessions[player] = state
    newWindow(state, now)
    player.CharacterAdded:Connect(function(character)
        if sessions[player] ~= state then return end
        state.character = character
        state.previousPosition = nil
        state.previousTime = nil
        state.previousContext = nil
        state.graceUntil = time() + 3
        state.approvedUntil = 0
        state.contextName = nil
        state.contextUntil = 0
    end)
end

local function movementContext(state, humanoid, now)
    if now < state.contextUntil then
        return state.contextName
    end
    -- Humanoid state and seating can be influenced by client-owned physics.
    -- They do not authorize a lenient context; only a server hook can do that.
    if humanoid.FloorMaterial == Enum.Material.Air then return "airborne" end
    return "grounded"
end

local function watchRemote(item)
    if not item:IsA("RemoteEvent") or watchedRemotes[item]
        or watchedRemoteCount >= MAX_WATCHED_REMOTES then return end
    watchedRemotes[item] = item.OnServerEvent:Connect(function(player)
        if emitted >= MAX_WINDOWS_PER_SERVER then return end
        local state = sessions[player]
        if state then
            state.remoteCount = math.min(state.remoteCount + 1, MAX_REMOTES_PER_WINDOW)
        end
    end)
    watchedRemoteCount += 1
end

for _, item in game:GetDescendants() do watchRemote(item) end
game.DescendantAdded:Connect(watchRemote)
game.DescendantRemoving:Connect(function(item)
    local connection = watchedRemotes[item]
    if connection then
        connection:Disconnect()
        watchedRemotes[item] = nil
        watchedRemoteCount -= 1
    end
end)

Players.PlayerAdded:Connect(attachPlayer)
Players.PlayerRemoving:Connect(function(player)
    local state = sessions[player]
    if state then emit(player, state) end
    sessions[player] = nil
end)
for _, player in Players:GetPlayers() do attachPlayer(player) end

local elapsed = 0
RunService.Heartbeat:Connect(function(dt)
    if emitted >= MAX_WINDOWS_PER_SERVER then return end
    elapsed += dt
    if elapsed < SAMPLE_SECONDS then return end
    elapsed = 0
    local now = time()
    for player, state in sessions do
        if now - state.windowStart >= WINDOW_SECONDS then
            emit(player, state)
            newWindow(state, now)
        end
        local character = player.Character
        local humanoid = character and character:FindFirstChildOfClass("Humanoid")
        local root = character and character:FindFirstChild("HumanoidRootPart")
        if not character or not humanoid or not root or humanoid.Health <= 0 then
            state.previousPosition = nil
            state.previousTime = nil
            state.previousContext = nil
            continue
        end
        if state.character ~= character then
            state.character = character
            state.previousPosition = nil
            state.previousTime = nil
            state.previousContext = nil
            state.graceUntil = now + 3
        end
        state.samples += 1
        -- Exemptions and custom contexts arrive through the server-only module,
        -- never through a replicated character attribute or a client claim.
        local ignored = now < state.graceUntil or now < state.approvedUntil
        local context = ignored and "approved" or movementContext(state, humanoid, now)
        local position = root.Position
        if not math.isfinite(position.X) or not math.isfinite(position.Y)
            or not math.isfinite(position.Z) then
            state.nonfiniteMovementCount = math.min(state.nonfiniteMovementCount + 1, 10000)
            state.previousPosition = nil
            state.previousTime = nil
            state.previousContext = nil
            continue
        end
        if state.previousPosition and state.previousTime then
            local gap = now - state.previousTime
            if gap > 0 and gap <= 1.5 and state.previousContext == context then
                if ignored then
                    state.ignoredMovement += 1
                else
                    local delta = position - state.previousPosition
                    local horizontal = Vector3.new(delta.X, 0, delta.Z).Magnitude / gap
                    local upward = math.max(0, delta.Y / gap)
                    if math.isfinite(horizontal) and math.isfinite(upward) then
                        local summary = state.movementContexts[context]
                        summary.samples += 1
                        summary.max_horizontal = math.max(summary.max_horizontal,
                            math.min(horizontal, 100000))
                        summary.max_upward = math.max(summary.max_upward,
                            math.min(upward, 100000))
                        state.maxHorizontal = math.max(state.maxHorizontal,
                            math.min(horizontal, 100000))
                        state.maxUpward = math.max(state.maxUpward,
                            math.min(upward, 100000))
                    else
                        state.nonfiniteMovementCount = math.min(state.nonfiniteMovementCount + 1, 10000)
                    end
                end
            end
        end
        state.previousPosition = position
        state.previousTime = now
        state.previousContext = context
    end
end)

game:BindToClose(function()
    for player, state in sessions do emit(player, state) end
end)
print("[ArthurAI pilot] Universal, review-only telemetry enabled; Output is session-local")
