//! Veltix wire protocol - framing constants and message (de)serialization.
//!
//! Pure-Rust mirror of `src/veltix/network/constants.py`, `request.py` and
//! `parser.py`. The wire format described here is the single source of truth
//! shared between the Python and Rust implementations.

pub mod error;

pub use error::ProtocolError;

/// Magic bytes identifying a Veltix frame.
pub const MAGIC: [u8; 2] = *b"VX";

/// Size of the request ID field in bytes.
pub const REQUEST_ID_SIZE: usize = 2;

// ── Header layout (15 bytes, big-endian) ──────────────────────────────────
//  Offset  Size  Field         Struct format
//  0       2     MAGIC         "2s"
//  2       1     flags         "B"
//  3       2     type code     "H"
//  5       4     content size  "I"
//  9       4     CRC32 hash    "4s"
//  13      2     request id    "2s"

pub const MAGIC_OFFSET: usize = 0;
pub const FLAGS_OFFSET: usize = 2;
pub const CODE_OFFSET: usize = 3;
pub const SIZE_OFFSET: usize = 5;
pub const HASH_OFFSET: usize = 9;
pub const REQUEST_ID_OFFSET: usize = 13;

/// Total header length in bytes.
pub const HEADER_SIZE: usize = REQUEST_ID_OFFSET + REQUEST_ID_SIZE;

/// Largest representable content size (uint32).
pub const MAX_CONTENT_SIZE: usize = u32::MAX as usize;

/// Default maximum accepted message size in bytes.
pub const DEFAULT_MAX_MESSAGE_SIZE: usize = 10 * 1024 * 1024;

/// A decoded Veltix frame.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Response {
    /// Protocol flags carried in the header.
    pub flags: u8,
    /// Message type code.
    pub type_code: u16,
    /// Raw content payload.
    pub content: Vec<u8>,
    /// CRC32 of the content as stored in the header.
    pub hash: [u8; 4],
    /// Request correlation ID.
    pub request_id: u16,
}

/// Serialize a message into wire format: 15-byte header + content.
///
/// Returns `ProtocolError::ContentTooLarge` if the content exceeds 4 GiB.
pub fn compile(
    type_code: u16,
    content: &[u8],
    request_id: u16,
    flags: u8,
) -> Result<Vec<u8>, ProtocolError> {
    let size = content.len();
    if size > MAX_CONTENT_SIZE {
        return Err(ProtocolError::ContentTooLarge {
            size,
            maximum: MAX_CONTENT_SIZE,
        });
    }

    let hash = crc32fast::hash(content).to_be_bytes();
    let mut buf = Vec::with_capacity(HEADER_SIZE + size);

    buf.extend_from_slice(&MAGIC);
    buf.push(flags);
    buf.extend_from_slice(&type_code.to_be_bytes());
    buf.extend_from_slice(&(size as u32).to_be_bytes());
    buf.extend_from_slice(&hash);
    buf.extend_from_slice(&request_id.to_be_bytes());
    buf.extend_from_slice(content);

    Ok(buf)
}

/// Parse raw bytes from the wire into a [`Response`].
///
/// Validates the magic bytes, size bounds, content size, and CRC32 hash.
pub fn parse(data: &[u8], max_message_size: usize) -> Result<Response, ProtocolError> {
    let len = data.len();

    if len < HEADER_SIZE {
        return Err(ProtocolError::TooShort {
            len,
            minimum: HEADER_SIZE,
        });
    }
    if len > max_message_size {
        return Err(ProtocolError::TooLarge {
            len,
            maximum: max_message_size,
        });
    }

    let header = &data[..HEADER_SIZE];
    let content = &data[HEADER_SIZE..];

    let magic = [header[MAGIC_OFFSET], header[MAGIC_OFFSET + 1]];
    if magic != MAGIC {
        return Err(ProtocolError::InvalidMagic { got: magic });
    }

    let flags = header[FLAGS_OFFSET];
    let type_code = u16::from_be_bytes([header[CODE_OFFSET], header[CODE_OFFSET + 1]]);
    let content_size = u32::from_be_bytes([
        header[SIZE_OFFSET],
        header[SIZE_OFFSET + 1],
        header[SIZE_OFFSET + 2],
        header[SIZE_OFFSET + 3],
    ]);

    if content.len() != content_size as usize {
        return Err(ProtocolError::SizeMismatch {
            expected: content_size as usize,
            got: content.len(),
        });
    }

    let hash = [
        header[HASH_OFFSET],
        header[HASH_OFFSET + 1],
        header[HASH_OFFSET + 2],
        header[HASH_OFFSET + 3],
    ];
    let request_id = u16::from_be_bytes([header[REQUEST_ID_OFFSET], header[REQUEST_ID_OFFSET + 1]]);

    if hash != crc32fast::hash(content).to_be_bytes() {
        return Err(ProtocolError::HashMismatch);
    }

    Ok(Response {
        flags,
        type_code,
        content: content.to_vec(),
        hash,
        request_id,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Decode a frame from its hexadecimal representation.
    fn hex(s: &str) -> Vec<u8> {
        (0..s.len())
            .step_by(2)
            .map(|i| u8::from_str_radix(&s[i..i + 2], 16).unwrap())
            .collect()
    }

    // Well-known frames mirrored from tests/protocol_vectors.py (Python).
    const HELLO: &str = "56580000c8000000053610a686123468656c6c6f";
    const EMPTY: &str = "565800000000000000000000000000";
    const UTF8: &str = "56580000c90000000b035d5cdeffff56656c74697820f09fa680";
    const PLUGIN_JSON: &str = "565800271000000010d2e71e5100017b226b223a205b312c20322c20335d7d";

    #[test]
    fn compile_matches_hello_vector() {
        let wire = compile(200, b"hello", 0x1234, 0).unwrap();
        assert_eq!(wire, hex(HELLO));
    }

    #[test]
    fn compile_matches_empty_vector() {
        let wire = compile(0, b"", 0, 0).unwrap();
        assert_eq!(wire, hex(EMPTY));
    }

    #[test]
    fn compile_matches_utf8_vector() {
        let wire = compile(201, "Veltix 🦀".as_bytes(), 0xFFFF, 0).unwrap();
        assert_eq!(wire, hex(UTF8));
    }

    #[test]
    fn compile_matches_plugin_json_vector() {
        let wire = compile(10000, br#"{"k": [1, 2, 3]}"#, 1, 0).unwrap();
        assert_eq!(wire, hex(PLUGIN_JSON));
    }

    #[test]
    fn compile_too_large_content() {
        let large = vec![0u8; MAX_CONTENT_SIZE + 1];
        let err = compile(1, &large, 0, 0).unwrap_err();
        assert_eq!(
            err,
            ProtocolError::ContentTooLarge {
                size: MAX_CONTENT_SIZE + 1,
                maximum: MAX_CONTENT_SIZE,
            }
        );
    }

    #[test]
    fn parse_hello_vector() {
        let resp = parse(&hex(HELLO), DEFAULT_MAX_MESSAGE_SIZE).unwrap();
        assert_eq!(resp.flags, 0);
        assert_eq!(resp.type_code, 200);
        assert_eq!(resp.content, b"hello");
        assert_eq!(resp.request_id, 0x1234);
        assert_eq!(resp.hash, [0x36, 0x10, 0xA6, 0x86]);
    }

    #[test]
    fn parse_empty_vector() {
        let resp = parse(&hex(EMPTY), DEFAULT_MAX_MESSAGE_SIZE).unwrap();
        assert_eq!(resp.type_code, 0);
        assert_eq!(resp.content, b"");
        assert_eq!(resp.request_id, 0);
    }

    #[test]
    fn parse_utf8_vector() {
        let resp = parse(&hex(UTF8), DEFAULT_MAX_MESSAGE_SIZE).unwrap();
        assert_eq!(resp.type_code, 201);
        assert_eq!(resp.content, "Veltix 🦀".as_bytes());
        assert_eq!(resp.request_id, 0xFFFF);
    }

    #[test]
    fn parse_plugin_json_vector() {
        let resp = parse(&hex(PLUGIN_JSON), DEFAULT_MAX_MESSAGE_SIZE).unwrap();
        assert_eq!(resp.type_code, 10000);
        assert_eq!(resp.content, br#"{"k": [1, 2, 3]}"#);
        assert_eq!(resp.request_id, 1);
    }

    #[test]
    fn parse_roundtrip() {
        let wire = compile(42, b"Hello, World!", 0xBEEF, 1).unwrap();
        let resp = parse(&wire, DEFAULT_MAX_MESSAGE_SIZE).unwrap();
        assert_eq!(resp.flags, 1);
        assert_eq!(resp.type_code, 42);
        assert_eq!(resp.content, b"Hello, World!");
        assert_eq!(resp.request_id, 0xBEEF);
    }

    #[test]
    fn parse_rejects_too_short() {
        let err = parse(b"VX", 1024).unwrap_err();
        assert!(matches!(err, ProtocolError::TooShort { .. }));
    }

    #[test]
    fn parse_rejects_too_large() {
        let err = parse(&hex(HELLO), 10).unwrap_err();
        assert!(matches!(err, ProtocolError::TooLarge { .. }));
    }

    #[test]
    fn parse_rejects_wrong_magic() {
        let mut data = hex(HELLO);
        data[0] = 0x00;
        data[1] = 0x00;
        let err = parse(&data, 1024).unwrap_err();
        assert!(matches!(err, ProtocolError::InvalidMagic { .. }));
    }

    #[test]
    fn parse_rejects_size_mismatch() {
        // Valid hello frame with 2 extra content bytes ("!!").
        let mut data = hex(HELLO);
        data.extend_from_slice(b"!!");
        let err = parse(&data, 1024).unwrap_err();
        assert!(matches!(err, ProtocolError::SizeMismatch { .. }));
    }

    #[test]
    fn parse_rejects_corrupted_hash() {
        // "hello" -> "hella" without updating the stored hash.
        let mut data = hex(HELLO);
        let last = data.len() - 1;
        data[last] = b'a';
        let err = parse(&data, 1024).unwrap_err();
        assert!(matches!(err, ProtocolError::HashMismatch));
    }
}
