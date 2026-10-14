// Validate event frames before handing them to the detector.
const std = @import("std");

const kinds = [_][]const u8{
    "login_ok", "list_objects", "read_object", "logout", "list_users",
    "login_fail", "assume_role", "read_secret", "bulk_download",
    "move_ok", "action_ok", "latency_spike", "movement_violation",
    "remote_reject", "reward_mismatch", "repetitive_timing",
};

fn knownKind(kind: []const u8) bool {
    for (kinds) |known| {
        if (std.mem.eql(u8, kind, known)) return true;
    }
    return false;
}

pub fn main() !void {
    const allocator = std.heap.page_allocator;
    const input = std.io.getStdIn().reader();
    const output = std.io.getStdOut().writer();
    var line_number: usize = 0;
    while (try input.readUntilDelimiterOrEofAlloc(allocator, '\n', 4096)) |allocated| {
        defer allocator.free(allocated);
        line_number += 1;
        const line = std.mem.trimRight(u8, allocated, "\r");
        var fields = std.mem.splitScalar(u8, line, '\t');
        const session = fields.next() orelse return error.InvalidFrame;
        const step_text = fields.next() orelse return error.InvalidFrame;
        const kind = fields.next() orelse return error.InvalidFrame;
        if (fields.next() != null or session.len == 0 or !knownKind(kind)) {
            std.log.err("invalid event frame at line {d}", .{line_number});
            return error.InvalidFrame;
        }
        const step = std.fmt.parseInt(usize, step_text, 10) catch {
            std.log.err("invalid step at line {d}", .{line_number});
            return error.InvalidFrame;
        };
        try output.print("{s}\t{d}\t{s}\n", .{ session, step, kind });
    }
}
