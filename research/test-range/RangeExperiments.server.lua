-- Two opt-in experiments: real Studio client isolation and normal-play trials.
-- Neither experiment bans players or sends data outside this server session.
local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local reviewSignal = script.Parent:WaitForChild("BayesGuardReviewSignal")

local WHITE = Color3.fromRGB(245, 245, 245)
local GREY = Color3.fromRGB(105, 105, 105)
local DARK = Color3.fromRGB(25, 25, 25)
local RETURN_POINT = CFrame.lookAt(Vector3.new(0, 7, 1180), Vector3.new(0, 7, 1400))
local TRIAL_SECONDS = 120
local MIN_ACTIVE_SECONDS = 20

local lab = Instance.new("Model")
lab.Name = "ArthurAI Live Experiments"
lab.Parent = workspace

local function makePost(name, position, action, display)
    local post = Instance.new("Part")
    post.Name = name
    post.Size = Vector3.new(4, 5, 4)
    post.Position = position
    post.Anchored = true
    post.CanCollide = true
    post.Color = WHITE
    post.Material = Enum.Material.SmoothPlastic
    post.Parent = lab

    local prompt = Instance.new("ProximityPrompt")
    prompt.ActionText = action
    prompt.ObjectText = name
    prompt.HoldDuration = 0
    prompt.MaxActivationDistance = 12
    prompt.Parent = post

    local gui = Instance.new("BillboardGui")
    gui.Adornee = post
    gui.AlwaysOnTop = true
    gui.Size = UDim2.fromOffset(330, 110)
    gui.StudsOffsetWorldSpace = Vector3.new(0, 6, 0)
    gui.Parent = post

    local text = Instance.new("TextLabel")
    text.Size = UDim2.fromScale(1, 1)
    text.BackgroundColor3 = DARK
    text.BackgroundTransparency = .05
    text.BorderColor3 = GREY
    text.BorderSizePixel = 1
    text.TextColor3 = WHITE
    text.Font = Enum.Font.Code
    text.TextScaled = true
    text.TextWrapped = true
    text.Text = display
    text.Parent = gui
    return prompt, text
end

local multiPrompt, multiText = makePost(
    "Two-player check", Vector3.new(-7, 3.5, 1187), "Test two players",
    "TWO-PLAYER CHECK\nUse Studio Server & Clients (2).\nOne moves; the other stays put.")
local trialPrompt, trialText = makePost(
    "Normal-play trial", Vector3.new(16, 3.5, 1187), "Start 2-minute trial",
    "NORMAL-PLAY TRIAL\nOpt in, then play the obby normally.\n0 completed / 0 reviewed")

local activeMulti = nil
local trials = {}
local completedTrials = 0
local reviewedTrials = 0
local trialReviewEvents = 0

reviewSignal.Event:Connect(function(player, _result)
    if activeMulti then
        if player == activeMulti.actor then activeMulti.actorReviews += 1 end
        if player == activeMulti.other then activeMulti.otherReviews += 1 end
    end
    local trial = trials[player]
    if trial then trial.reviews += 1 end
end)

local function giveGrace(character)
    character:SetAttribute("BayesGuardMovementGraceUntil", time() + 4)
end

multiPrompt.Triggered:Connect(function(actor)
    if not RunService:IsStudio() then
        multiText.Text = "TWO-PLAYER CHECK\nStudio only. No live player is moved."
        return
    end
    if activeMulti then return end
    local other
    for _, player in Players:GetPlayers() do
        if player ~= actor then other = player break end
    end
    if not other then
        multiText.Text = "TWO-PLAYER CHECK\nStart Studio with 2 clients first."
        return
    end
    if trials[actor] or trials[other] then
        multiText.Text = "TWO-PLAYER CHECK\nFinish normal-play trials first."
        return
    end
    local character = actor.Character
    local root = character and character:FindFirstChild("HumanoidRootPart")
    if not root or not root:IsA("BasePart") then return end

    activeMulti = { actor = actor, other = other, actorReviews = 0, otherReviews = 0 }
    local experiment = activeMulti
    multiText.Text = "TWO-PLAYER CHECK\nRunning... second player stay still."
    task.spawn(function()
        -- Studio server moves only actor A. This checks the real Player adapter's
        -- per-player state, not whether an actual exploit can bypass the server.
        local origin = character:GetPivot()
        local wasAnchored = root.Anchored
        root.Anchored = true
        task.wait(5) -- Let spawn/teleport grace expire and sample a baseline.
        if actor.Parent ~= Players or other.Parent ~= Players or actor.Character ~= character then
            root.Anchored = wasAnchored
            activeMulti = nil
            multiText.Text = "TWO-PLAYER CHECK\nCancelled: player left or respawned."
            return
        end
        for i = 1, 8 do
            local offset = (i % 2 == 1) and 210 or 0
            character:PivotTo(origin + Vector3.new(0, 0, offset))
            task.wait(.7)
        end
        giveGrace(character)
        character:PivotTo(origin)
        root.Anchored = wasAnchored
        task.wait(1)
        local ok = experiment.actorReviews > 0 and experiment.otherReviews == 0
        multiText.Text = string.format("TWO-PLAYER CHECK: %s\nA reviews: %d | B reviews: %d",
            ok and "PASS" or "FAIL", experiment.actorReviews, experiment.otherReviews)
        print(string.format("[ArthurAI multi-client] %s: moving player reviews=%d, stationary player reviews=%d",
            ok and "PASS" or "FAIL", experiment.actorReviews, experiment.otherReviews))
        activeMulti = nil
    end)
end)

local function obbySpawn()
    for _, item in workspace:GetDescendants() do
        if item:IsA("SpawnLocation") and not item:IsDescendantOf(lab) then
            return item
        end
    end
    return nil
end

local function showTrialTotals()
    local rate = completedTrials > 0 and string.format("%.1f%%", 100 * reviewedTrials / completedTrials) or "n/a"
    trialText.Text = string.format(
        "NORMAL-PLAY TRIAL\n%d complete | %d reviewed (%s)\n%s",
        completedTrials, reviewedTrials, rate,
        "Proxy only, not a proven false-alarm rate")
end

trialPrompt.Triggered:Connect(function(player)
    if trials[player] then return end
    if activeMulti then
        trialText.Text = "NORMAL-PLAY TRIAL\nFinish the two-player check first."
        return
    end
    local spawn = obbySpawn()
    if not spawn then
        trialText.Text = "NORMAL-PLAY TRIAL\nNo obby SpawnLocation found."
        return
    end
    local character = player.Character
    local humanoid = character and character:FindFirstChildOfClass("Humanoid")
    if not character or not humanoid or humanoid.Health <= 0 then return end
    local root = character:FindFirstChild("HumanoidRootPart")
    if not root or not root:IsA("BasePart") then return end
    local trial = { character = character, reviews = 0, activeSeconds = 0 }
    trials[player] = trial
    giveGrace(character)
    character:PivotTo(spawn.CFrame + Vector3.new(0, 5, 0))
    print(string.format("[ArthurAI trial] %s opted in: play normally for %d seconds", player.Name, TRIAL_SECONDS))
    task.spawn(function()
        local previous = root.Position
        for _ = 1, TRIAL_SECONDS do
            task.wait(1)
            if trials[player] ~= trial or player.Character ~= character then return end
            local current = root.Position
            if (current - previous).Magnitude >= 1 then
                trial.activeSeconds += 1
            end
            previous = current
        end
    end)
    task.delay(TRIAL_SECONDS, function()
        if trials[player] ~= trial then return end
        trials[player] = nil
        if player.Parent ~= Players or player.Character ~= character or humanoid.Health <= 0
            or trial.activeSeconds < MIN_ACTIVE_SECONDS then
            print(string.format("[ArthurAI trial] Incomplete/idle trial excluded (%d active seconds)", trial.activeSeconds))
            return
        end
        completedTrials += 1
        trialReviewEvents += trial.reviews
        if trial.reviews > 0 then reviewedTrials += 1 end
        showTrialTotals()
        giveGrace(character)
        character:PivotTo(RETURN_POINT)
        print(string.format("[ArthurAI trial] Completed: %d sessions, %d with review, %d review events; manual legitimacy check required",
            completedTrials, reviewedTrials, trialReviewEvents))
    end)
end)

Players.PlayerRemoving:Connect(function(player)
    trials[player] = nil
end)

print("[ArthurAI] Live experiments ready: two-player Studio check and opt-in normal-play trial")
