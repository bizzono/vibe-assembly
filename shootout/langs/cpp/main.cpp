// Shootout driver (C++). See shootout/PROTOCOL.md.
#include <charconv>
#include <chrono>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <iostream>
#include <limits>
#include <memory>
#include <optional>
#include <span>
#include <string_view>
#include <system_error>
#include <vector>

// The kernel: one of the sibling <kernel>.cpp files, chosen at build time.
std::uint64_t run(std::span<const std::uint8_t> data);
std::uint64_t digest();

namespace {

using Clock = std::chrono::steady_clock;

std::uint64_t ns_since(Clock::time_point start) {
    const auto elapsed = Clock::now() - start;
    return static_cast<std::uint64_t>(std::chrono::duration_cast<std::chrono::nanoseconds>(elapsed).count());
}

// Reads the whole file with one fread, as the C driver does. (An ifstream copies
// everything through its small buffer, about 1 ms more for the 8 MiB inputs.)
std::optional<std::vector<std::uint8_t>> read_file(const char* path) {
    const std::unique_ptr<std::FILE, int (*)(std::FILE*)> file{std::fopen(path, "rb"), &std::fclose};
    if (!file) return std::nullopt;
    if (std::fseek(file.get(), 0, SEEK_END) != 0) return std::nullopt;
    const long size = std::ftell(file.get());
    if (size < 0 || std::fseek(file.get(), 0, SEEK_SET) != 0) return std::nullopt;
    std::vector<std::uint8_t> bytes(static_cast<std::size_t>(size));
    if (std::fread(bytes.data(), 1, bytes.size(), file.get()) != bytes.size()) return std::nullopt;
    return bytes;
}

std::optional<std::uint64_t> parse_u64(std::string_view text) {
    std::uint64_t value = 0;
    const auto [end, err] = std::from_chars(text.data(), text.data() + text.size(), value);
    if (err != std::errc{} || end != text.data() + text.size()) return std::nullopt;
    return value;
}

}  // namespace

int main(int argc, char** argv) {
    if (argc != 3) {
        std::cerr << "usage: " << (argc > 0 ? argv[0] : "prog") << " <input-file> <min_ms>\n";
        return 2;
    }
    const auto input = read_file(argv[1]);
    if (!input) {
        std::cerr << argv[1] << ": read failed\n";
        return 2;
    }
    const auto min_ms = parse_u64(argv[2]);
    if (!min_ms) {
        std::cerr << "min_ms must be a non-negative integer\n";
        return 2;
    }
    const std::span<const std::uint8_t> data{*input};
    const std::uint64_t min_ns = *min_ms * 1'000'000;

    if (min_ns == 0) {  // cold mode: one call, no digest
        const auto start = Clock::now();
        const std::uint64_t result = run(data);
        const std::uint64_t ns = ns_since(start);
        std::cout << "RESULT " << result << " 0 " << ns << " 1\n";
        return 0;
    }

    const std::uint64_t warm = run(data);
    std::uint64_t result = warm;
    std::uint64_t best = std::numeric_limits<std::uint64_t>::max();
    std::uint64_t total = 0;
    std::uint64_t calls = 0;
    while (calls < 3 || (total < min_ns && calls < 1'000'000)) {
        const auto start = Clock::now();
        result = run(data);
        const std::uint64_t ns = ns_since(start);
        if (result != warm) {
            std::cerr << "result changed between calls\n";
            return 3;
        }
        if (ns < best) best = ns;
        total += ns;
        ++calls;
    }
    std::cout << "RESULT " << result << ' ' << digest() << ' ' << best << ' ' << calls << '\n';
    return 0;
}
