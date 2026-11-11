# frozen_string_literal: true

# wordcount kernel (Ruby): port of tasks/wordcount/ref.c.
module ShootoutKernel
  def self.run(data)
    words = 0
    in_word = false
    data.each_byte do |c|
      if c == 0x20 || (c >= 0x09 && c <= 0x0D) # space, \t \n \v \f \r
        in_word = false
      elsif !in_word
        in_word = true
        words += 1
      end
    end
    words
  end

  def self.digest
    0
  end
end
