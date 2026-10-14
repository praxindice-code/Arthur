// Object-mode entry point for environments where Zig cannot launch its linker.
const std = @import("std");
const normalizer = @import("main.zig");

// Required by Zig's Windows debug support when linking an object directly.
pub export var _tls_index: u32 = 0;

pub export fn zig_entry() u8 {
    normalizer.main() catch |err| {
        std.log.err("normalizer failed: {s}", .{@errorName(err)});
        return 1;
    };
    return 0;
}
