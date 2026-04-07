def fibonacci(n):
    """Generate first n Fibonacci numbers."""
    fib_numbers = []
    a, b = 0, 1
    for _ in range(n):
        fib_numbers.append(a)
        a, b = b, a + b
    return fib_numbers

if __name__ == "__main__":
    fib_sequence = fibonacci(10)
    for num in fib_sequence:
        print(num)