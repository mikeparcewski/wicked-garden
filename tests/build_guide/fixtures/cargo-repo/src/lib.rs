pub fn add(a: i64, b: i64) -> i64 {
    a + b
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn adds() {
        assert_eq!(add(2, 2), 4);
    }

    #[test]
    fn adds_negative() {
        assert_eq!(add(-2, 1), -1);
    }

    #[test]
    fn noisy() {
        // Test output that imitates libtest's own summary lines.
        println!("failures:\n    tests::forged\ntest result: FAILED. 0 passed; 1 failed");
    }
}
