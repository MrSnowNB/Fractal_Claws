#!/usr/bin/env python3
"""Generate 20 Fibonacci numbers and save to file."""

def generate_fibonacci(n):
    """Generate first n Fibonacci numbers."""
    fib = []
    a, b = 0, 1
    for _ in range(n):
        fib.append(a)
        a, b = b, a + b
    return fib

def main():
    fib_numbers = generate_fibonacci(20)
    
    with open('output/fib.txt', 'w') as f:
        for num in fib_numbers:
            f.write(f"{num}\n")
    
    print(f"Generated {len(fib_numbers)} Fibonacci numbers")
    print(f"Saved to output/fib.txt")

if __name__ == "__main__":
    main()