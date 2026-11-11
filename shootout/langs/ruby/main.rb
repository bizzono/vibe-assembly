# frozen_string_literal: true

# Shootout driver (Ruby). See shootout/PROTOCOL.md.
#
#   ruby main.rb <kernel.rb> <input-file> <min_ms>
#
# The kernel file defines the module ShootoutKernel with two module methods:
# ShootoutKernel.run(data) -- data is a binary String -- and ShootoutKernel.digest.

if ARGV.length != 3
  warn "usage: ruby main.rb <kernel.rb> <input-file> <min_ms>"
  exit 2
end

require File.expand_path(ARGV[0])

U64 = 0xFFFFFFFFFFFFFFFF

def now_ns
  Process.clock_gettime(Process::CLOCK_MONOTONIC, :nanosecond)
end

data = File.binread(ARGV[1])
min_ns = Integer(ARGV[2], 10) * 1_000_000

if min_ns == 0 # cold mode: one call, no digest
  t0 = now_ns
  result = ShootoutKernel.run(data)
  best = now_ns - t0
  puts "RESULT #{result & U64} 0 #{best} 1"
  exit 0
end

warm = ShootoutKernel.run(data)
result = warm
best = nil
total = 0
calls = 0
while calls < 3 || (total < min_ns && calls < 1_000_000)
  t0 = now_ns
  result = ShootoutKernel.run(data)
  dt = now_ns - t0
  if result != warm
    warn "result changed between calls"
    exit 3
  end
  best = dt if best.nil? || dt < best
  total += dt
  calls += 1
end
puts "RESULT #{result & U64} #{ShootoutKernel.digest & U64} #{best} #{calls}"
