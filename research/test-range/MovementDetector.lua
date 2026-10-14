-- Pure movement-sequence logic shared by live players and the test-range dummies.
-- This is a review signal, not proof of cheating or a ban decision.
local MovementDetector = {}
MovementDetector.__index = MovementDetector

local MAX_SAMPLE_GAP = 1.5
local MAX_HORIZONTAL_SPEED = 125
local MAX_UPWARD_SPEED = 150
local FLAG_WINDOW = 12
local FLAGS_FOR_REVIEW = 3
local REVIEW_COOLDOWN = 20

function MovementDetector.new()
    return setmetatable({ actors = {} }, MovementDetector)
end

function MovementDetector:reset(actor)
    self.actors[actor] = nil
end

function MovementDetector:observe(actor, now, position, context)
    local state = self.actors[actor]
    if not state then
        self.actors[actor] = {
            position = position,
            time = now,
            flags = {},
            lastReview = -math.huge,
        }
        return { kind = "baseline", review = false, flagCount = 0 }
    end

    local dt = now - state.time
    local delta = position - state.position
    state.position = position
    state.time = now
    if dt <= 0 or dt > MAX_SAMPLE_GAP then
        return { kind = "gap", review = false, flagCount = #state.flags }
    end
    if context and context.ignore then
        return { kind = "ignored", review = false, flagCount = #state.flags }
    end

    local horizontal = Vector3.new(delta.X, 0, delta.Z).Magnitude / dt
    local upward = delta.Y / dt -- A long fall is not an upward movement cheat.
    if horizontal <= MAX_HORIZONTAL_SPEED and upward <= MAX_UPWARD_SPEED then
        return {
            kind = "normal", review = false, flagCount = #state.flags,
            horizontal = horizontal, upward = upward,
        }
    end

    table.insert(state.flags, now)
    while #state.flags > 0 and now - state.flags[1] > FLAG_WINDOW do
        table.remove(state.flags, 1)
    end
    local review = #state.flags >= FLAGS_FOR_REVIEW
        and now - state.lastReview >= REVIEW_COOLDOWN
    if review then
        state.lastReview = now
    end
    return {
        kind = "large_move", review = review, flagCount = #state.flags,
        horizontal = horizontal, upward = upward,
    }
end

return MovementDetector
