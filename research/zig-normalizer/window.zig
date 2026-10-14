// Bounded feature extraction linked into the Rust live service through C ABI.
// No heap allocation and no client-supplied pointers outside the caller's slice.
pub const WindowCounts = extern struct {
    movement: u32,
    remote: u32,
    reward: u32,
    timing: u32,
};

export fn bg_window_counts(events: [*]const u8, len: usize, out: *WindowCounts) void {
    var counts = WindowCounts{ .movement = 0, .remote = 0, .reward = 0, .timing = 0 };
    const bounded = @min(len, 32);
    for (events[0..bounded]) |event| {
        switch (event) {
            3 => counts.movement += 1,
            4 => counts.remote += 1,
            5 => counts.reward += 1,
            6 => counts.timing += 1,
            else => {},
        }
    }
    out.* = counts;
}

test "counts known events in bounded window" {
    const std = @import("std");
    const input = [_]u8{ 0, 3, 4, 5, 6, 3 };
    var counts: WindowCounts = undefined;
    bg_window_counts(&input, input.len, &counts);
    try std.testing.expectEqual(@as(u32, 2), counts.movement);
    try std.testing.expectEqual(@as(u32, 1), counts.remote);
    try std.testing.expectEqual(@as(u32, 1), counts.reward);
    try std.testing.expectEqual(@as(u32, 1), counts.timing);
}
