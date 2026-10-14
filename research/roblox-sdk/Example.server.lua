-- Put this server Script beside BayesGuard in ServerScriptService.
-- Enable HTTP requests in Experience Settings > Security first.
local HttpService = game:GetService("HttpService")
local BayesGuard = require(script.Parent.BayesGuard)

local guard = BayesGuard.new({
    url = "https://YOUR-HTTPS-GATEWAY.example",
    key = HttpService:GetSecret("BayesGuardKey"),
    onAlert = function(player, score, sessionId)
        -- Review-only example. Do not automatically kick or ban.
        warn("BayesGuard review signal", player.UserId, score, sessionId)
    end,
})
guard:start()

-- Call guard:record(player, kind) in *your own server-side validators*.
-- Example: after checking a purchase against server-held balance and price:
-- if not purchaseIsValid then
--     guard:record(player, "reward_mismatch")
--     return
-- end
-- guard:record(player, "action_ok")
