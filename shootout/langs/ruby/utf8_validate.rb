# frozen_string_literal: true

# utf8_validate kernel (Ruby): port of tasks/utf8_validate/ref.c, a direct
# transcription of Table 3-7 ("Well-Formed UTF-8 Byte Sequences") of the Unicode Standard.
module ShootoutKernel
  def self.run(s)
    n = s.bytesize
    i = 0
    while i < n
      c = s.getbyte(i)
      if c < 0x80
        i += 1
      elsif c >= 0xC2 && c <= 0xDF
        return 0 if n - i < 2
        c1 = s.getbyte(i + 1)
        return 0 unless c1 >= 0x80 && c1 <= 0xBF
        i += 2
      elsif c >= 0xE0 && c <= 0xEF
        lo = c == 0xE0 ? 0xA0 : 0x80 # E0: no overlong encodings
        hi = c == 0xED ? 0x9F : 0xBF # ED: no UTF-16 surrogates
        return 0 if n - i < 3
        c1 = s.getbyte(i + 1)
        return 0 unless c1 >= lo && c1 <= hi
        c2 = s.getbyte(i + 2)
        return 0 unless c2 >= 0x80 && c2 <= 0xBF
        i += 3
      elsif c >= 0xF0 && c <= 0xF4
        lo = c == 0xF0 ? 0x90 : 0x80 # F0: no overlong encodings
        hi = c == 0xF4 ? 0x8F : 0xBF # F4: nothing above U+10FFFF
        return 0 if n - i < 4
        c1 = s.getbyte(i + 1)
        return 0 unless c1 >= lo && c1 <= hi
        c2 = s.getbyte(i + 2)
        return 0 unless c2 >= 0x80 && c2 <= 0xBF
        c3 = s.getbyte(i + 3)
        return 0 unless c3 >= 0x80 && c3 <= 0xBF
        i += 4
      else
        return 0 # 80..C1 and F5..FF never start a sequence
      end
    end
    1
  end

  def self.digest
    0
  end
end
