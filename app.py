import socket
print ("hello world")

hostname = socket.gethostname()
print(f"Hostname: {hostname}")

IPaddress = socket.gethostbyname(hostname)
print(f"IP Address: {IPaddress}")

for i in range(10):
     print(f"count {i}")
     
numero_a = input("dame el primer numero: ")
numero_b = input("dame el segundo numero: ")
print(f"la suma es: {int(numero_a) + int(numero_b)}")
print("adios mundo")

print(f"la resta es: {int(numero_a) - int(numero_b)}")

print(f"la multiplicacion es: {int(numero_a) * int(numero_b)}")