use std::convert::TryInto;

pub struct MessageBuffer {
    buffer: Vec<u8>,
    max_message_size: usize,
}

impl MessageBuffer {
    pub fn new(max_message_size: usize) -> Self {
        MessageBuffer {
            buffer: Vec::new(),
            max_message_size,
        }
    }

    pub fn add_data(&mut self, data: &[u8]) {
        self.buffer.extend_from_slice(data);
    }

    pub fn extract_messages(&mut self) -> Vec<Vec<u8>> {
        let mut messages = Vec::new();

        loop {
            if self.buffer.len() < 16 {
                break;
            }
            let content_size: u32 = u32::from_be_bytes(self.buffer[4..8].try_into().unwrap());
            let total_size = 16 + content_size as usize;
            if total_size > self.max_message_size {
                eprintln!(
                    "Message size {} exceeds maximum {}",
                    total_size, self.max_message_size
                );
                self.clear();
                break;
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
        // Header (16 bytes): MAGIC b"VX" + code 200 + size 5 + CRC32 hash + req_id
        // Content: b"hello"
        let data: &[u8] = &[
            86, 88, 0, 200, 0, 0, 0, 5, 54, 16, 166, 134, 1, 2, 3, 4, 104, 101, 108, 108, 111,
        ];
        buffer.add_data(data);
        let messages = buffer.extract_messages();
        assert_eq!(messages.len(), 1);
        assert_eq!(messages[0], data);
    }
}
