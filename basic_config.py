import serial
import time
import pandas as pd
import os
import re

# 🔹 Limpiar pantalla según el SO
def clear_console():
    if os.name == 'nt':
        os.system('cls')
    else:
        os.system('clear')

# 🔹 Enviar comando al router (versión mejorada)
def send_command(ser, command, base_delay=2, max_retries=3):
    ser.reset_input_buffer()
    ser.write((command + "\r\n").encode())

    output = ""
    delay = base_delay

    for intento in range(max_retries):
        time.sleep(delay)
        chunk = ser.read(ser.in_waiting).decode(errors="ignore")
        if chunk:
            output += chunk
            # 🔄 seguir leyendo hasta que ya no llegue nada nuevo
            while True:
                time.sleep(0.5)
                more = ser.read(ser.in_waiting).decode(errors="ignore")
                if not more:
                    break
                output += more
            break
        else:
            # ⏳ si no hubo respuesta, aumentar delay y reintentar
            delay += 2  

    if not output.strip():
        return "⚠ No hubo respuesta del dispositivo."

    return output

# 🔹 Obtener número de serie desde "show inventory"
def get_serial(ser):
    send_command(ser, "terminal length 0")  # evitar paginación
    output = send_command(ser, "show inventory", base_delay=3)
    match = re.search(r"SN:\s*([A-Z0-9]+)", output)
    if match:
        return match.group(1)
    return None

# 🔹 Configuración de dispositivo
def configure_device(port, hostname, user, password, domain):
    try:
        ser = serial.Serial(port, baudrate=9600, timeout=1)
        time.sleep(2)
        print(f"\n🔗 Conectado al dispositivo en {port} ({hostname})")

        serial_num = get_serial(ser)
        if not serial_num:
            print("⚠ No se pudo obtener el número de serie. Saltando configuración.")
            ser.close()
            return False

        if hostname[1:] != serial_num:
            print(f"⚠ La serie del dispositivo ({serial_num}) no coincide con la del CSV ({hostname[1:]}). Saltando configuración.")
            ser.close()
            return False

        send_command(ser, "enable")
        send_command(ser, "configure terminal")
        send_command(ser, f"hostname {hostname}")
        send_command(ser, f"username {user} privilege 15 secret {password}")
        send_command(ser, f"ip domain-name {domain}")
        send_command(ser, "crypto key generate rsa modulus 1024", base_delay=5)
        send_command(ser, "line vty 0 4")
        send_command(ser, "login local")
        send_command(ser, "transport input ssh")
        send_command(ser, "transport output ssh")
        send_command(ser, "exit")
        send_command(ser, "ip ssh version 2")
        send_command(ser, "end")
        send_command(ser, "write memory", base_delay=3)

        print(f"✅ Configuración aplicada correctamente en {hostname}.")
        ser.close()
        return True

    except Exception as e:
        print(f"❌ Error al configurar el dispositivo {hostname}: {e}")
        return False

# 🔹 Menú principal
def mostrar_menu():
    clear_console()
    print("=== MENÚ PRINCIPAL ===")
    print("1. Mandar comandos manualmente")
    print("2. Hacer configuraciones iniciales desde CSV")
    print("0. Salir")

# 🔹 Menú de comandos manuales
def menu_comandos_manual():
    port = input("🔌 Ingresa el puerto serial (ej. COM3): ")
    try:
        ser = serial.Serial(port, baudrate=9600, timeout=1)
        time.sleep(2)
        print(f"\n✅ Conectado al dispositivo en {port}")
        while True:
            cmd = input("📥 Ingresa el comando (o 'exit' para salir): ")
            if cmd.lower() == "exit":
                break
            output = send_command(ser, cmd, base_delay=3)
            print(f"\n📤 Respuesta:\n{output}")
        ser.close()
    except Exception as e:
        print(f"❌ Error al conectar: {e}")
    input("Presione ENTER para volver al menú...")

# 🔹 Flujo de configuración inicial
def flujo_configuracion_csv():
    clear_console()
    df = pd.read_csv(r"C:\Users\jessu\OneDrive\Documentos\venv\Data.csv")
    print("\n📂 Dispositivos encontrados en el archivo:")
    print(df)

    Hostnames = [str(d).strip()[0] + str(s).strip() for d, s in zip(df['Device'], df['Serie'])]
    list_device = [(p, h, u, pas, dom) for p, u, pas, dom, h in zip(df['Port'], df['User'], df['Password'], df['Ip-domain'], Hostnames)]

    print("\n📋 Lista de dispositivos y sus configuraciones:")
    for item in list_device:
        print(item)
    input("Presione ENTER para continuar...")

    configured_devices = []
    skipped_devices = []

    for idx, (p, h, u, pas, dom) in enumerate(list_device, start=1):
        clear_console()
        print(f"\n➡ Conecte ahora el dispositivo {idx}: {h} en el puerto {p}")
        input("Presione ENTER cuando el dispositivo esté conectado...")
        success = configure_device(p, h, u, pas, dom)
        if success:
            configured_devices.append(h)
        else:
            skipped_devices.append(h)
        print("=================================================")
        input("Presione ENTER para continuar...")

    clear_console()
    print("📊 Resumen de la configuración:")
    print(f"✅ Dispositivos configurados ({len(configured_devices)}): {configured_devices}")
    print(f"⚠ Dispositivos saltados ({len(skipped_devices)}): {skipped_devices}")
    input("Presione ENTER para volver al menú...")

# 🔹 Ejecutar menú
if __name__ == "__main__":
    while True:
        mostrar_menu()
        opcion = input("Selecciona una opción: ")
        if opcion == "1":
            menu_comandos_manual()
        elif opcion == "2":
            flujo_configuracion_csv()
        elif opcion == "0":
            print("👋 Saliendo del programa...")
            break
        else:
            print("❌ Opción inválida.")
            input("Presione ENTER para continuar...")
