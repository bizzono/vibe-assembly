//! wordcount kernel (Zig): port of tasks/wordcount/ref.c.

fn isSpace(c: u8) bool {
    return c == ' ' or (c >= '\t' and c <= '\r'); // space, \t \n \v \f \r
}

fn wordcount(buf: []const u8) u64 {
    var words: u64 = 0;
    var in_word = false;
    for (buf) |c| {
        if (isSpace(c)) {
            in_word = false;
        } else if (!in_word) {
            in_word = true;
            words += 1;
        }
    }
    return words;
}

pub fn run(data: []const u8) u64 {
    return wordcount(data);
}

pub fn digest() u64 {
    return 0;
}
