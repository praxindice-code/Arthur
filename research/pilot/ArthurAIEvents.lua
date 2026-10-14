-- Optional server-only hooks for ArthurAIUniversal.server.lua.
-- Put this ModuleScript beside ArthurAIUniversal in ServerScriptService.
-- Never expose it through a RemoteEvent or let a client choose the event kind.
local Players = game:GetService("Players")

local ArthurAIEvents = {}
local sink = nil
local allowed = {
    remote_reject = true,
    reward_mismatch = true,
    invalid_hit = true,
}
local allowedContexts = {ragdoll = true, vehicle = true}

local function validPlayer(player)
    return typeof(player) == "Instance" and player:IsA("Player")
        and player.Parent == Players
end

local function validSeconds(seconds)
    return type(seconds) == "number" and math.isfinite(seconds)
        and seconds > 0 and seconds <= 30
end

function ArthurAIEvents.bind(callback)
    assert(type(callback) == "function", "server callback required")
    assert(sink == nil, "ArthurAI event sink already bound")
    sink = callback
end

function ArthurAIEvents.record(player, kind)
    if not validPlayer(player) then
        return false
    end
    if not allowed[kind] or sink == nil then
        return false
    end
    sink(player, kind)
    return true
end

-- Call immediately before a legitimate server-driven teleport, dash, or launch.
-- The collector stores this exemption privately; no replicated attribute is trusted.
function ArthurAIEvents.allowMovement(player, seconds)
    if not validPlayer(player) or sink == nil then
        return false
    end
    if not validSeconds(seconds) then
        return false
    end
    sink(player, "approved_movement", seconds)
    return true
end

-- For custom server-authoritative mechanics not visible from Humanoid state.
-- The caller must have verified the player is really in this mode.
function ArthurAIEvents.setMovementContext(player, context, seconds)
    if not validPlayer(player) or sink == nil or not allowedContexts[context]
        or not validSeconds(seconds) then
        return false
    end
    sink(player, "movement_context", {name = context, seconds = seconds})
    return true
end

return ArthurAIEvents
