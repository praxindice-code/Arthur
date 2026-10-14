-- A playable, review-only test range. The visible dummies are test actors,
-- not Roblox Player objects. Both they and the live adapter use MovementDetector.
local Players = game:GetService("Players")
local MovementDetector = require(script.Parent.MovementDetector)

local RANGE_Z = 1400
local START_Z = 1210
local WHITE = Color3.fromRGB(245, 245, 245)
local GREY = Color3.fromRGB(105, 105, 105)
local DARK = Color3.fromRGB(25, 25, 25)

local range = Instance.new("Model")
range.Name = "ArthurAI Test Range"
range.Parent = workspace

local function part(name, size, position, color, parent, collides)
    local item = Instance.new("Part")
    item.Name = name
    item.Size = size
    item.Position = position
    item.Color = color
    item.Material = Enum.Material.SmoothPlastic
    item.Anchored = true
    item.CanCollide = collides == true
    item.Parent = parent
    return item
end

local function label(adornee, text, width, height)
    local gui = Instance.new("BillboardGui")
    gui.Name = "ResultLabel"
    gui.Adornee = adornee
    gui.AlwaysOnTop = true
    gui.Size = UDim2.fromOffset(width, height)
    gui.StudsOffsetWorldSpace = Vector3.new(0, 4, 0)
    gui.Parent = adornee

    local words = Instance.new("TextLabel")
    words.Name = "Text"
    words.Size = UDim2.fromScale(1, 1)
    words.BackgroundColor3 = DARK
    words.BackgroundTransparency = 0.08
    words.BorderSizePixel = 1
    words.BorderColor3 = WHITE
    words.TextColor3 = WHITE
    words.Font = Enum.Font.Code
    words.TextScaled = true
    words.TextWrapped = true
    words.Text = text
    words.Parent = gui
    return words
end

part("Black floor", Vector3.new(370, 2, 480), Vector3.new(0, 0, RANGE_Z), DARK, range, true)
part("Starting line", Vector3.new(355, 0.2, 2), Vector3.new(0, 1.1, START_Z), WHITE, range, false)
local board = part("Summary board", Vector3.new(26, 9, 1), Vector3.new(0, 20, 1230), GREY, range, false)
local summary = label(board, "ARTHURAI TEST RANGE\nPreparing tests...", 470, 130)

local promptPost = part("Run tests again", Vector3.new(4, 5, 4), Vector3.new(7, 3.5, 1187), WHITE, range, true)
local prompt = Instance.new("ProximityPrompt")
prompt.ActionText = "Run tests again"
prompt.ObjectText = "ArthurAI Test Range"
prompt.HoldDuration = 0
prompt.MaxActivationDistance = 12
prompt.Parent = promptPost

local function makeDummy(name, x)
    part(name .. " lane", Vector3.new(15, 0.15, 390), Vector3.new(x, 1.1, 1410), GREY, range, false)
    local model = Instance.new("Model")
    model.Name = name .. " dummy"
    model.Parent = range
    local torso = part("Torso", Vector3.new(2.5, 3, 1.5), Vector3.new(x, 4, START_Z), WHITE, model, false)
    local head = part("Head", Vector3.new(1.7, 1.7, 1.7), Vector3.new(x, 6.3, START_Z), GREY, model, false)
    head.Shape = Enum.PartType.Ball
    model.PrimaryPart = torso
    local words = label(head, name .. "\nPENDING", 220, 80)
    return { model = model, words = words, x = x }
end

local function sample(t, z, y, ignored, actor)
    return { t = t, pos = Vector3.new(0, y or 0, z), ignored = ignored == true, actor = actor }
end

local scenarios = {
    {
        name = "Normal run", expected = false,
        samples = { sample(0, 0), sample(.5, 10), sample(1, 20), sample(1.5, 30), sample(2, 40) },
    },
    {
        name = "Fast dash", expected = false,
        samples = { sample(0, 0), sample(.5, 30), sample(1, 60), sample(1.5, 90), sample(2, 120) },
    },
    {
        name = "Long fall", expected = false,
        samples = { sample(0, 0, 100), sample(.5, 0, 0), sample(1, 10, -100), sample(1.5, 20, -200) },
    },
    {
        name = "Spawn grace", expected = false,
        samples = { sample(0, 0), sample(.5, 200, 0, true), sample(1, 0, 0, true), sample(1.5, 200, 0, true) },
    },
    {
        name = "Moving platform", expected = false,
        samples = { sample(0, 0), sample(.5, 200, 0, true), sample(1, 0, 0, true), sample(1.5, 200, 0, true) },
    },
    {
        name = "One odd jump", expected = false,
        samples = { sample(0, 0), sample(.5, 200), sample(1, 200), sample(1.5, 200), sample(2, 200) },
    },
    {
        name = "Repeat teleport", expected = true,
        samples = { sample(0, 0), sample(.5, 200), sample(1, 0), sample(1.5, 200), sample(2, 0) },
    },
    {
        name = "Repeat upward", expected = true,
        samples = { sample(0, 0), sample(.5, 0, 100), sample(1, 0, 0), sample(1.5, 0, 100), sample(2, 0, 0), sample(2.5, 0, 100) },
    },
    {
        name = "Speed boundary", expected = false,
        samples = { sample(0, 0), sample(1, 125), sample(2, 250), sample(3, 375) },
    },
    {
        name = "Long sample gap", expected = false,
        samples = { sample(0, 0), sample(2, 500), sample(4, 0), sample(6, 500) },
    },
    {
        name = "Expired spikes", expected = false,
        samples = { sample(0, 0), sample(1, 200), sample(13, 200), sample(14, 400), sample(26, 400), sample(27, 600) },
    },
    {
        name = "Reset history", expected = false,
        samples = { sample(0, 0), sample(.5, 200), sample(1, 0),
            { reset = true }, sample(1.5, 0), sample(2, 200), sample(2.5, 0) },
    },
    {
        name = "Review cooldown", expected = true, expectedReviews = 1,
        samples = { sample(0, 0), sample(.5, 200), sample(1, 0), sample(1.5, 200),
            sample(2, 0), sample(2.5, 200), sample(3, 0) },
    },
    {
        name = "Actor isolation", expected = true, expectedOtherReviews = 0,
        samples = { sample(0, 0, 0, false, "A"), sample(0, 0, 0, false, "B"),
            sample(.5, 200, 0, false, "A"), sample(.5, 10, 0, false, "B"),
            sample(1, 0, 0, false, "A"), sample(1, 20, 0, false, "B"),
            sample(1.5, 200, 0, false, "A"), sample(1.5, 30, 0, false, "B") },
    },
}

local dummies = {}
for index, scenario in scenarios do
    dummies[index] = makeDummy(scenario.name, -168 + (index - 1) * 24)
end

local running = false
local function runTests()
    if running then return end
    running = true
    local detector = MovementDetector.new()
    local passed = 0
    local failed = 0
    summary.Text = "ARTHURAI TEST RANGE\nRunning dummy scenarios..."
    for index, scenario in scenarios do
        local dummy = dummies[index]
        dummy.words.Text = scenario.name .. "\nRUNNING"
        local reviewCount = 0
        local otherReviews = 0
        local largeMoves = 0
        for _, entry in scenario.samples do
            if entry.reset then
                detector:reset(scenario.name)
                dummy.words.Text = scenario.name .. "\nRESET"
            else
                local actor = entry.actor and (scenario.name .. entry.actor) or scenario.name
                local result = detector:observe(actor, entry.t, entry.pos, { ignore = entry.ignored })
                if result.kind == "large_move" then largeMoves += 1 end
                if result.review then
                    if entry.actor == "B" then otherReviews += 1
                    else reviewCount += 1 end
                end
                if entry.actor ~= "B" then
                    -- Visual height is compressed, while detection uses the full coordinates.
                    local visualY = math.clamp(entry.pos.Y * 0.1, 0, 15)
                    dummy.model:PivotTo(CFrame.new(dummy.x, 4 + visualY, START_Z + entry.pos.Z))
                end
            end
            task.wait(0.18)
        end
        local ok = (reviewCount > 0) == scenario.expected
            and (not scenario.expectedReviews or reviewCount == scenario.expectedReviews)
            and (not scenario.expectedOtherReviews or otherReviews == scenario.expectedOtherReviews)
        if ok then passed += 1 else failed += 1 end
        dummy.words.Text = string.format("%s\n%s | %d large moves", scenario.name, ok and "PASS" or "FAIL", largeMoves)
        print(string.format("[ArthurAI range] %s: %s (reviews=%d, other=%d, expected=%s)",
            scenario.name, ok and "PASS" or "FAIL", reviewCount, otherReviews, tostring(scenario.expected)))
        summary.Text = string.format("ARTHURAI TEST RANGE\n%d PASS / %d FAIL / %d TOTAL",
            passed, failed, #scenarios)
        task.wait(0.2)
    end
    range:SetAttribute("Passed", passed)
    range:SetAttribute("Failed", failed)
    range:SetAttribute("Complete", true)
    summary.Text = string.format("ARTHURAI TEST RANGE\n%d / %d PASS\nE to replay | review only", passed, #scenarios)
    print(string.format("[ArthurAI range] Complete: %d/%d pass; no bans or network upload", passed, #scenarios))
    running = false
end

prompt.Triggered:Connect(function(_player)
    task.spawn(runTests)
end)

local function movePlayerToRange(player)
    player.CharacterAdded:Connect(function(character)
        local root = character:WaitForChild("HumanoidRootPart", 5)
        if not root then return end
        task.wait(0.2)
        character:SetAttribute("BayesGuardMovementGraceUntil", time() + 4)
        character:PivotTo(CFrame.lookAt(Vector3.new(0, 7, 1180), Vector3.new(0, 7, RANGE_Z)))
    end)
end
Players.PlayerAdded:Connect(movePlayerToRange)
for _, player in Players:GetPlayers() do
    movePlayerToRange(player)
end

task.delay(2, runTests)
print(string.format("[ArthurAI range] Arena created; %d dummy checks will run automatically", #scenarios))
