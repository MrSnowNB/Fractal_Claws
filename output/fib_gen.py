def generate_fibonacci(n):
fib = []
a, b = 0, 1
for i in range(n):
fib.append(a)
a, b = b, a + b
return fib

if __name__ == "__main__":
fib_numbers = generate_fibonacci(20)
with open("output/fib.txt", "w") as f:
f.write("First 20 Fibonacci numbers:\n")
for i, num in enumerate(fib_numbers, 1):
f.write(f"{i}. {num}\n")
print("Fibonacci numbers saved to output/fib.txt")