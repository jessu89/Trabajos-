import serial
import serial.tools.list_ports
import time
import pandas as pd
import os
import re

# ╔════════════════════════════════════════════════════════════════╗
#   FUNCIONES AUXILIARES
# ╚════════════════════════════════════════════════════════════════╝

def clear_console():
    os.system("cls" if os.name == "nt" else "clear")

def listar_puertos():
    """Lista los puertos disponibles."""
    return list(serial.tools.list_ports.comports())

def conectar_dispositivo():
    """Intenta conectar al primer puerto disponible."""
    while True:
        puertos = listar_puertos()
        if not puertos:
            print("❌ No se detectaron puertos disponibles. Conecta un dispositivo...")
            time.sleep(2)
            continue

        print("\n🔍 Puertos detectados:")
        for i, p in enumerate(puertos, 1):
            print(f"{i}. {p.device} - {p.description}")

        try:
            port = puertos[0].device  # Toma el primero automáticamente
            ser = serial.Serial(port, baudrate=9600, timeout=1)
            time.sleep(2)
            print(f"\n✅ Conectado al dispositivo en {port}")
            return ser
        except Exception as e:
            print(f"❌ Error al conectar en {port}: {e}")
            time.sleep(2)

def send_command(ser, command, base_delay=2, max_retries=3):
    ser.reset_input_buffer()
    ser.write((command + "\r\n").encode())

    output, delay = "", base_delay
    for intento in range(max_retries):
        time.sleep(delay)
        chunk = ser.read(ser.in_waiting).decode(errors="ignore")

        if chunk:
            output += chunk
            while True:
                time.sleep(0.5)
                more = ser.read(ser.in_waiting).decode(errors="ignore")
                if not more:
                    break
                output += more
            break
        else:
            delay += 2

    return output.strip() if output.strip() else "⚠ No hubo respuesta del dispositivo."

def get_serial(ser):
    send_command(ser, "terminal length 0")
    output = send_command(ser, "show inventory", base_delay=3)
    match = re.search(r"SN:\s*([A-Z0-9]+)", output)
    return match.group(1) if match else None

# ╔════════════════════════════════════════════════════════════════╗
#   CONFIGURACIÓN DE DISPOSITIVO
# ╚════════════════════════════════════════════════════════════════╝

def configure_device(ser, hostname, user, password, domain):
    try:
        print(f"\n🔗 Configurando dispositivo: {hostname}")

        serial_num = get_serial(ser)
        if not serial_num:
            print("⚠ No se pudo obtener el número de serie. Saltando...")
            return False

        if hostname[1:] != serial_num:
            print(f"⚠ Serie del dispositivo ({serial_num}) ≠ Esperada ({hostname[1:]})")
            return False

        comandos = [
            "enable",
            "configure terminal",
            f"hostname {hostname}",
            f"username {user} privilege 15 secret {password}",
            f"ip domain-name {domain}",
            "crypto key generate rsa modulus 1024",
            "line vty 0 4",
            "login local",
            "transport input ssh",
            "transport output ssh",
            "exit",
            "ip ssh version 2",
            "end",
            "write memory"
        ]

        for cmd in comandos:
            delay = 5 if "crypto key" in cmd or "write memory" in cmd else 2
            send_command(ser, cmd, base_delay=delay)

        print(f"✅ Configuración aplicada correctamente en {hostname}")
        return True

    except Exception as e:
        print(f"❌ Error al configurar {hostname}: {e}")
        return False

# ╔════════════════════════════════════════════════════════════════╗
#   MENÚS
# ╚════════════════════════════════════════════════════════════════╝

def mostrar_menu():
    clear_console()
    print("""
╔════════════════════════════════════════════════╗
║                 MENÚ PRINCIPAL                 ║
╚════════════════════════════════════════════════╝
1. Mandar comandos manualmente
2. Hacer configuraciones iniciales desde CSV
0. Salir
""")

def menu_comandos_manual(ser):
    while True:
        cmd = input("📥 Ingresa el comando (o 'exit' para salir): ")
        if cmd.lower() == "exit":
            break
        output = send_command(ser, cmd, base_delay=3)
        print(f"\n📤 Respuesta:\n{output}")
    input("Presione ENTER para volver al menú...")

def flujo_configuracion_csv(ser):
    clear_console()
    df = pd.read_csv(r"C:\Users\jessu\OneDrive\Documentos\venv\Data.csv")

    print("\n📂 Dispositivos en archivo CSV:")
    print(df)

    Hostnames = [str(d).strip()[0] + str(s).strip() for d, s in zip(df["Device"], df["Serie"])]
    dispositivos = [(h, u, pas, dom) for u, pas, dom, h in zip(
        df["User"], df["Password"], df["Ip-domain"], Hostnames
    )]

    print("\n📋 Lista de dispositivos:")
    for dev in dispositivos:
        print(dev)
    input("Presione ENTER para continuar...")

    configurados, saltados = [], []

    for idx, (h, u, pas, dom) in enumerate(dispositivos, start=1):
        clear_console()
        print(f"\n➡ Configurando dispositivo {idx}: {h}")
        if configure_device(ser, h, u, pas, dom):
            configurados.append(h)
        else:
            saltados.append(h)
        print("=================================================")
        input("Presione ENTER para continuar...")

    clear_console()
    print("📊 Resumen de configuración:")
    print(f"✅ Configurados ({len(configurados)}): {configurados}")
    print(f"⚠ Saltados ({len(saltados)}): {saltados}")
    input("Presione ENTER para volver al menú...")

# ╔════════════════════════════════════════════════════════════════╗
#   MAIN LOOP
# ╚════════════════════════════════════════════════════════════════╝

if __name__ == "__main__":
    ser = conectar_dispositivo()

    while True:
        try:
            mostrar_menu()
            opcion = input("Selecciona una opción: ")
            if opcion == "1":
                menu_comandos_manual(ser)
            elif opcion == "2":
                flujo_configuracion_csv(ser)
            elif opcion == "0":
                print("👋 Cerrando conexión y saliendo...")
                ser.close()
                break
            else:
                print("❌ Opción inválida.")
                input("Presione ENTER para continuar...")
        except serial.SerialException:
            print("\n⚠ Conexión perdida. Intentando reconectar...")
            ser = conectar_dispositivo()
