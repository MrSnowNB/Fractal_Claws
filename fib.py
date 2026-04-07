#!/usr/bin/env python3
def fibonacci(n):
    fibs = []
    a, b = 1, 1
    for i in range(n):
        fibs.append(a)
        a, b = b, a + b
    return fibs

for num in fibonacci(10):
    print(num)