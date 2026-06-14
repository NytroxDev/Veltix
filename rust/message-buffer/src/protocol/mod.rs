pub mod error;

use error::ProtocolError;

const MAX_CONTENT_SIZE: usize = u32::MAX as usize;

pub const MAGIC: &[u8; 2] = b"VX";
pub const HEADER_SIZE: usize = 16;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Response {
    pub type_code: u16,
    pub content: Vec<u8>,
    pub hash: [u8; 4],
    pub request_id: [u8; 4],
}

/// Serialize a message into wire format: header (16 bytes) + content.
///
/// Returns `ProtocolError::ContentTooLarge` if content exceeds 4 GiB.
pub fn compile(
    type_code: u16,
    content: &[u8],
    request_id: &[u8; 4],
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

    buf.extend_from_slice(MAGIC);
    buf.extend_from_slice(&type_code.to_be_bytes());
    buf.extend_from_slice(&(size as u32).to_be_bytes());
    buf.extend_from_slice(&hash);
    buf.extend_from_slice(request_id);
    buf.extend_from_slice(content);

    Ok(buf)
}

/// Parse raw bytes from the wire into a `Response`.
///
/// Validates magic bytes, size bounds, content size, and CRC32 hash.
pub fn parse(data: &[u8], max_message_size: usize) -> Result<Response, ProtocolError> {
    let size = data.len();

    if size < HEADER_SIZE {
        return Err(ProtocolError::TooShort {
            len: size,
            minimum: HEADER_SIZE,
        });
    }
    if size > max_message_size {
        return Err(ProtocolError::TooLarge {
            len: size,
            maximum: max_message_size,
        });
    }

    let header = &data[..HEADER_SIZE];
    let content = &data[HEADER_SIZE..];

    if header[..2] != *MAGIC {
        return Err(ProtocolError::InvalidMagic {
            got: [header[0], header[1]],
        });
    }

    let type_code = u16::from_be_bytes([header[2], header[3]]);
    let content_size = u32::from_be_bytes([header[4], header[5], header[6], header[7]]);

    if content.len() != content_size as usize {
        return Err(ProtocolError::SizeMismatch {
            expected: content_size as usize,
            got: content.len(),
        });
    }

    let hash = [header[8], header[9], header[10], header[11]];
    let request_id = [header[12], header[13], header[14], header[15]];

    let computed = crc32fast::hash(content).to_be_bytes();
    if hash != computed {
        return Err(ProtocolError::HashMismatch);
    }

    Ok(Response {
        type_code,
        content: content.to_vec(),
        hash,
        request_id,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    fn hex(s: &str) -> Vec<u8> {
        (0..s.len())
            .step_by(2)
            .map(|i| u8::from_str_radix(&s[i..i + 2], 16).unwrap())
            .collect()
    }

    #[test]
    fn compile_basic() {
        let rid = [1, 2, 3, 4];
        let result = compile(200, b"hello", &rid).unwrap();

        let expected = hex("565800c8000000053610a6860102030468656c6c6f");
        assert_eq!(result, expected);
    }

    #[test]
    fn compile_empty_content() {
        let rid = [0, 0, 0, 0];
        let result = compile(0, b"", &rid).unwrap();

        let mut expected = b"VX".to_vec();
        expected.extend_from_slice(&0u16.to_be_bytes());
        expected.extend_from_slice(&0u32.to_be_bytes());
        expected.extend_from_slice(&crc32fast::hash(b"").to_be_bytes());
        expected.extend_from_slice(&[0, 0, 0, 0]);
        assert_eq!(result, expected);
        assert_eq!(result.len(), HEADER_SIZE);
    }

    #[test]
    fn compile_too_large_content() {
        let large = vec![0u8; MAX_CONTENT_SIZE + 1];
        let err = compile(1, &large, &[0; 4]).unwrap_err();
        assert_eq!(
            err,
            ProtocolError::ContentTooLarge {
                size: MAX_CONTENT_SIZE + 1,
                maximum: MAX_CONTENT_SIZE,
            }
        );
    }

    #[test]
    fn parse_valid_message() {
        let data = hex("565800c8000000053610a6860102030468656c6c6f");
        let resp = parse(&data, 10 * 1024 * 1024).unwrap();

        assert_eq!(resp.type_code, 200);
        assert_eq!(resp.content, b"hello");
        assert_eq!(resp.hash, [0x36, 0x10, 0xA6, 0x86]);
        assert_eq!(resp.request_id, [1, 2, 3, 4]);
    }

    #[test]
    fn parse_roundtrip() {
        let rid = [0xDE, 0xAD, 0xBE, 0xEF];
        let wire = compile(42, b"Hello, World!", &rid).unwrap();
        let resp = parse(&wire, 10 * 1024 * 1024).unwrap();

        assert_eq!(resp.type_code, 42);
        assert_eq!(resp.content, b"Hello, World!");
        assert_eq!(resp.request_id, rid);
    }

    #[test]
    fn parse_rejects_too_short() {
        let err = parse(b"VX", 1024).unwrap_err();
        assert!(matches!(err, ProtocolError::TooShort { .. }));
    }

    #[test]
    fn parse_rejects_too_large() {
        let data = hex("565800c8000000053610a6860102030468656c6c6f");
        let err = parse(&data, 10).unwrap_err();
        assert!(matches!(err, ProtocolError::TooLarge { .. }));
    }

    #[test]
    fn parse_rejects_wrong_magic() {
        let data = hex("000000c8000000053610a6860102030468656c6c6f");
        let err = parse(&data, 1024).unwrap_err();
        assert!(matches!(err, ProtocolError::InvalidMagic { .. }));
    }

    #[test]
    fn parse_rejects_size_mismatch() {
        // content_size = 5 but actual content is "hello!!" (7 bytes)
        let data = hex("565800c8000000053610a6860102030468656c6c6f2121");
        let err = parse(&data, 1024).unwrap_err();
        assert!(matches!(err, ProtocolError::SizeMismatch { .. }));
    }

    #[test]
    fn parse_rejects_corrupted_hash() {
        // Same as valid, but content changed: "hello" -> "hella" without updating hash
        let data = hex("565800c8000000053610a6860102030468656c6c61");
        let err = parse(&data, 1024).unwrap_err();
        assert!(matches!(err, ProtocolError::HashMismatch));
    }
}
