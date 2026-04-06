#!/usr/bin/env python3
def generate_fibonacci(n):
fib = []
a, b = 0, 1
for _ in range(n):
fib.append(a)
a, b = b, a + b
return fib

def main():
n = 20
fib_numbers = generate_fibonacci(n)

with open('output/fib.txt', 'w') as f:
for num in fib_numbers:
f.write(f"{num}\n")

print(f"Generated {n} Fibonacci numbers and saved to output/fib.txt")

if __name__ == "__main__":
main()