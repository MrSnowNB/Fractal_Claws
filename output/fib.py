def generate_fibonacci(n):
fib = [0, 1]
for i in range(2, n):
fib.append(fib[i-1] + fib[i-2])
return fib

fib_numbers = generate_fibonacci(20)

with open('output/fib.txt', 'w') as f:
f.write('First 20 Fibonacci numbers:\n')
for i, num in enumerate(fib_numbers, 1):
f.write(f'{i}. {num}\n')

print(fib_numbers)