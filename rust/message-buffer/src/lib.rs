use std::convert::TryInto;

const MAGIC: [u8; 2] = [86, 88]; // b"VX"
const HEADER_SIZE: usize = 16;

pub struct MessageBuffer {
    buffer: Vec<u8>,
    max_message_size: usize,
    max_buffer_size: usize,
}

impl MessageBuffer {
    pub fn new(max_message_size: usize) -> Self {
        MessageBuffer {
            buffer: Vec::new(),
            max_message_size,
            max_buffer_size: 20 * 1024 * 1024,
        }
    }

    pub fn with_config(max_message_size: usize, max_buffer_size: usize) -> Self {
        MessageBuffer {
            buffer: Vec::new(),
            max_message_size,
            max_buffer_size,
        }
    }

    pub fn add_data(&mut self, data: &[u8]) {
        if data.len() + self.buffer.len() > self.max_buffer_size {
            self.clear()
        }
        self.buffer.extend_from_slice(data);
    }

    pub fn extract_messages(&mut self) -> Vec<Vec<u8>> {
        let mut messages = Vec::new();

        loop {
            if self.buffer.len() < HEADER_SIZE {
                break;
            }
            if self.buffer[0..2] != MAGIC {
                self._resync();
                continue;
            }
            let content_size: u32 = u32::from_be_bytes(self.buffer[4..8].try_into().unwrap());
            let total_size = HEADER_SIZE + content_size as usize;
            if total_size > self.max_message_size {
                eprintln!(
                    "Message size {} exceeds maximum {}",
                    total_size, self.max_message_size
                );
                self._resync();
                continue;
            }
            if self.buffer.len() < total_size {
                break;
            }
            let message_data: Vec<u8> = self.buffer[0..total_size].try_into().unwrap();
            self.buffer.drain(0..total_size);
            messages.push(message_data);
        }

        messages
    }

    pub fn _resync(&mut self) {
        if let Some(idx) = self.buffer[1..].windows(2).position(|w| w == MAGIC) {
            self.buffer.drain(..idx + 1);
        } else {
            self.clear();
        }
    }

    pub fn clear(&mut self) {
        self.buffer.clear();
    }

    pub fn len(&self) -> usize {
        self.buffer.len()
    }

    pub fn is_empty(&self) -> bool {
        self.buffer.is_empty()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn buffer_is_empty_on_start() {
        let buffer = MessageBuffer::new(10 * 1024 * 1024);
        assert!(buffer.is_empty());
    }

    #[test]
    fn buffer_has_data() {
        let mut buffer = MessageBuffer::new(10 * 1024 * 1024);
        let data: &[u8] = &[0, 1, 2, 3];
        buffer.add_data(data);
        assert_eq!(buffer.len(), 4);
    }

    #[test]
    fn extract_one_message() {
        let mut buffer = MessageBuffer::new(10 * 1024 * 1024);
        let data: &[u8] = &[
            86, 88, 0, 200, 0, 0, 0, 5, 54, 16, 166, 134, 1, 2, 3, 4, 104, 101, 108, 108, 111,
        ];
        buffer.add_data(data);
        let messages = buffer.extract_messages();
        assert_eq!(messages.len(), 1);
        assert_eq!(messages[0], data);
    }

    #[test]
    fn corrupted_prefix_then_valid() {
        let mut buffer = MessageBuffer::new(10 * 1024 * 1024);
        let mut data = vec![0xDE, 0xAD, 0xBE, 0xEF, 0xFF, 0xFF];
        // Valid message: b"world"
        data.extend_from_slice(&[
            86, 88, 0, 200, 0, 0, 0, 5, 58, 119, 17, 67, 1, 2, 3, 4, 119, 111, 114, 108, 100,
        ]);
        buffer.add_data(&data);
        let messages = buffer.extract_messages();
        assert_eq!(messages.len(), 1);
        assert_eq!(messages[0][0..2], [86, 88]);
    }

    #[test]
    fn two_messages_in_one_buffer() {
        let mut buffer = MessageBuffer::new(10 * 1024 * 1024);
        let msg1: &[u8] = &[
            86, 88, 0, 200, 0, 0, 0, 5, 54, 16, 166, 134, 1, 2, 3, 4, 104, 101, 108, 108, 111,
        ];
        let msg2: &[u8] = &[
            86, 88, 0, 200, 0, 0, 0, 5, 58, 119, 17, 67, 1, 2, 3, 4, 119, 111, 114, 108, 100,
        ];
        let mut combined = msg1.to_vec();
        combined.extend_from_slice(msg2);
        buffer.add_data(&combined);
        let messages = buffer.extract_messages();
        assert_eq!(messages.len(), 2);
        assert_eq!(messages[0], msg1);
        assert_eq!(messages[1], msg2);
    }

    #[test]
    fn partial_header_preserved() {
        let mut buffer = MessageBuffer::new(10 * 1024 * 1024);
        buffer.add_data(&[86, 88, 0, 200]); // only 4 bytes, need 16
        let messages = buffer.extract_messages();
        assert!(messages.is_empty());
        assert_eq!(buffer.len(), 4);
    }

    #[test]
    fn partial_content_preserved() {
        let mut buffer = MessageBuffer::new(10 * 1024 * 1024);
        let mut data = vec![86, 88, 0, 200, 0, 0, 0, 5, 54, 16, 166, 134, 1, 2, 3, 4];
        data.extend_from_slice(b"he"); // only 2 of 5 content bytes
        buffer.add_data(&data);
        let messages = buffer.extract_messages();
        assert!(messages.is_empty());
        assert_eq!(buffer.len(), 18);
    }

    #[test]
    fn size_exceeds_max_triggers_resync() {
        let mut buffer = MessageBuffer::new(50); // small max
        let large: &[u8] = &[
            86, 88, 0, 200, 0, 0, 0, 100, 153, 136, 198, 202, 1, 2, 3, 4, 0, 0, 0, 0, 0, 0, 0, 0,
            0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
            0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
            0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
            0, 0, 0, 0, 0, 0, 0, 0, 0,
        ];
        buffer.add_data(large);
        let messages = buffer.extract_messages();
        assert!(messages.is_empty());
        // Buffer should be empty after resync with no MAGIC past the first
        assert!(buffer.is_empty());
    }

    #[test]
    fn no_magic_found_clears_buffer() {
        let mut buffer = MessageBuffer::new(10 * 1024 * 1024);
        buffer.add_data(&[
            0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E,
            0x0F, 0x10, 0x11, 0x12,
        ]);
        let messages = buffer.extract_messages();
        assert!(messages.is_empty());
        assert!(buffer.is_empty());
    }
}

pub mod binding;
