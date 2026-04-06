def generate_fibonacci(n):
fib = []
a, b = 0, 1
for i in range(n):
fib.append(a)
a, b = b, a + b
return fib

fib_numbers = generate_fibonacci(20)

with open('output/fib.txt', 'w') as f:
for num in fib_numbers:
f.write(str(num) + '\n')