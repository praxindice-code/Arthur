-- Place this ModuleScript in ServerScriptService, never ReplicatedStorage.
-- This is review-only telemetry. The game must validate actions itself.
local HttpService = game:GetService("HttpService")
local Players = game:GetService("Players")

local BayesGuard = {}
BayesGuard.__index = BayesGuard

local allowed = {
    move_ok = true,
    action_ok = true,
    latency_spike = true,
    movement_violation = true,
    remote_reject = true,
    reward_mismatch = true,
    repetitive_timing = true,
}

function BayesGuard.new(config)
    assert(type(config) == "table", "config is required")
    assert(type(config.url) == "string" and string.sub(config.url, 1, 8) == "https://",
        "a hosted HTTPS endpoint is required")
    assert(config.key ~= nil, "use HttpService:GetSecret for the API key")
    local self = setmetatable({
        url = config.url,
        key = config.key,
        onAlert = config.onAlert,
        queue = {},
        sessions = {},
        playersBySession = {},
        alertedSessions = {},
        flushing = false,
        running = false,
    }, BayesGuard)
    return self
end

function BayesGuard:record(player, kind)
    assert(allowed[kind], "unknown BayesGuard event kind")
    -- Call only from a server Script *after* the game's own validation.
    if not player or not player:IsA("Player") then return false end
    local session = self.sessions[player]
    if not session then
        local id = tostring(game.GameId) .. ":" .. HttpService:GenerateGUID(false)
        session = { id = id, nextStep = 0 }
        self.sessions[player] = session
        self.playersBySession[id] = player
    end
    if #self.queue >= 250 then return false end -- bounded memory on network failure
    table.insert(self.queue, session.id .. "\t" .. session.nextStep .. "\t" .. kind)
    session.nextStep += 1
    return true
end

function BayesGuard:flush()
    if self.flushing or #self.queue == 0 then return end
    self.flushing = true
    local batch = {}
    for _ = 1, math.min(#self.queue, 50) do
        table.insert(batch, table.remove(self.queue, 1))
    end
    local ok, result = pcall(function()
        return HttpService:RequestAsync({
            Url = self.url .. "/v1/events",
            Method = "POST",
            Headers = {
                ["Content-Type"] = "text/plain",
                ["x-api-key"] = self.key,
            },
            Body = table.concat(batch, "\n") .. "\n",
        })
    end)
    self.flushing = false
    if not ok or not result.Success then
        local retry = batch
        for _, line in self.queue do table.insert(retry, line) end
        self.queue = retry
        warn("BayesGuard telemetry batch was not delivered; will retry; gameplay continues")
        return
    end
    if type(self.onAlert) ~= "function" then return end
    for line in string.gmatch(result.Body, "[^\n]+") do
        local id, _, score, alert = string.match(line, "^([^\t]+)\t(%d+)\t([^\t]+)\t([01])$")
        if alert == "1" and not self.alertedSessions[id] then
            self.alertedSessions[id] = true
            local player = self.playersBySession[id]
            if player and player.Parent == Players then
                -- Do not kick or ban here; this score has not been calibrated.
                self.onAlert(player, tonumber(score), id)
            end
        end
    end
end

function BayesGuard:start()
    if self.running then return end
    self.running = true
    Players.PlayerRemoving:Connect(function(player)
        local session = self.sessions[player]
        self.sessions[player] = nil
        if session then
            self.playersBySession[session.id] = nil
            self.alertedSessions[session.id] = nil
        end
    end)
    task.spawn(function()
        while self.running do
            task.wait(5)
            self:flush()
        end
    end)
    game:BindToClose(function()
        self.running = false
        self:flush()
    end)
end

return BayesGuard
