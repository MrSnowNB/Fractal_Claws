def generate_fibonacci(n):
    """Generate the first n Fibonacci numbers."""
    if n <= 0:
        return []
    if n == 1:
        return [0]
    
    fib = [0, 1]
    for i in range(2, n):
        fib.append(fib[i-1] + fib[i-2])
    return fib

def main():
    n = 20
    fib_numbers = generate_fibonacci(n)
    
    output_path = "output/fib.txt"
    with open(output_path, "w") as f:
        f.write("\n".join(str(num) for num in fib_numbers))
    
    print(f"Generated {n} Fibonacci numbers and saved to {output_path}")
    
    # Verification
    with open(output_path, "r") as f:
        lines = f.readlines()
    
    if len(lines) == n:
        print(f"Verification successful: file contains {n} lines")
    else:
        print(f"Verification failed: expected {n} lines, got {len(lines)}")

if __name__ == "__main__":
    main()