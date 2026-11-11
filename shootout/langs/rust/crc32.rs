//! crc32 kernel (Rust). A port of tasks/crc32/ref.c: the textbook table-driven
//! CRC-32, one table lookup per input byte. The table is built at compile time.

const fn make_crc_table() -> [u32; 256] {
    let mut table = [0u32; 256];
    let mut i = 0;
    while i < 256 {
        let mut c = i as u32;
        let mut bit = 0;
        while bit < 8 {
            c = if c & 1 != 0 { 0xEDB8_8320 ^ (c >> 1) } else { c >> 1 }; // reflected polynomial
            bit += 1;
        }
        table[i] = c;
        i += 1;
    }
    table
}

static CRC_TABLE: [u32; 256] = make_crc_table();
const _: () = assert!(CRC_TABLE[1] == 0x7707_3096 && CRC_TABLE[255] == 0x2d02_ef8d);

fn crc32_ieee(buf: &[u8]) -> u64 {
    let mut crc = 0xFFFF_FFFFu32;
    for &byte in buf {
        crc = CRC_TABLE[((crc ^ u32::from(byte)) & 0xFF) as usize] ^ (crc >> 8);
    }
    u64::from(crc ^ 0xFFFF_FFFF)
}

pub fn run(data: &[u8]) -> u64 {
    crc32_ieee(data)
}

pub fn digest() -> u64 {
    0
}
