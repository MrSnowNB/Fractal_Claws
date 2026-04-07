a, b = 0, 1
print(a)
for _ in range(9):
    a, b = b, a + b
    print(a)