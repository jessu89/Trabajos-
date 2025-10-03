import os
import sys
import serial
import serial.tools.list_ports
import time
import pandas as pd
import textfsm

# ╔════════════════════════════════════════════════════════════════╗
#   CONFIGURAR AUTOMÁTICAMENTE NET_TEXTFSM
# ╚════════════════════════════════════════════════════════════════╝

def setup_ntc_templates():
    """
    Detecta automáticamente la ruta de ntc_templates dentro del venv
    y la asigna a la variable de entorno NET_TEXTFSM.
    """
    try:
        import ntc_templates
        templates_path = os.path.join(os.path.dirname(ntc_templates.__file__), "templates")
        if os.path.isdir(templates_path):
            os.environ["NET_TEXTFSM"] = templates_path
            print(f"✅ NET_TEXTFSM detectado: {templates_path}")
        else:
            print("⚠ No se encontró la carpeta 'templates' dentro de ntc_templates.")
    except ImportError:
        print("❌ No está instalado ntc-templates. Instala con: pip install ntc-templates")
        sys.exit(1)

# Inicializamos NET_TEXTFSM
setup_ntc_templates()

# ╔════════════════════════════════════════════════════════════════╗
#   FUNCIONES AUXILIARES
# ╚════════════════════════════════════════════════════════════════╝

def clear_console():
    os.system("cls" if os.name == "nt" else "clear")

def listar_puertos():
    return list(serial.tools.list_ports.comports())

def conectar_dispositivo():
    while True:
        puertos = listar_puertos()
        if not puertos:
            print("❌ No se detectaron puertos. Conecta un dispositivo...")
            time.sleep(2)
            continue
        print("\nPuertos detectados:")
        for i, p in enumerate(puertos, 1):
            print(f"{i}. {p.device} - {p.description}")
        try:
            port = puertos[0].device
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
    for _ in range(max_retries):
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

# ╔════════════════════════════════════════════════════════════════╗
#   TEXTFSM PARA PARSEAR OUTPUTS
# ╚════════════════════════════════════════════════════════════════╝

def parse_with_textfsm(template_path, raw_output):
    with open(template_path) as template_file:
        fsm = textfsm.TextFSM(template_file)
        results = fsm.ParseText(raw_output)
        headers = fsm.header
    return pd.DataFrame(results, columns=headers)

def get_ports_status_update_csv(ser, csv_path):
    """
    Obtiene estado de puertos y actualiza directamente el CSV existente.
    """
    send_command(ser, "terminal length 0")
    raw_output = send_command(ser, "show interfaces status", base_delay=3)
    template = os.path.join(os.environ["NET_TEXTFSM"], "cisco_ios_show_interfaces_status.textfsm")

    try:
        df_ports = parse_with_textfsm(template, raw_output)
        print("\n📊 Estado de los puertos:")
        print(df_ports)

        # Leer CSV existente
        df_csv = pd.read_csv(csv_path)

        # Agregar todas las columnas nuevas del parse
        for col in df_ports.columns:
            df_csv[col] = df_ports[col].values[:len(df_csv)]

        # Guardar CSV actualizado
        df_csv.to_csv(csv_path, index=False)
        print(f"\n✅ CSV actualizado en {csv_path}")

    except Exception as e:
        print(f"⚠ Error al parsear el estado de los puertos: {e}")

# ╔════════════════════════════════════════════════════════════════╗
#   CONFIGURACIÓN DE DISPOSITIVO
# ╚════════════════════════════════════════════════════════════════╝

def configure_device(ser, hostname, user, password, domain):
    """
    Configura un dispositivo Cisco conectado por serial.
    """
    try:
        print(f"\n🔗 Configurando dispositivo: {hostname}")

        # Obtener número de serie con TextFSM
        send_command(ser, "terminal length 0")
        output = send_command(ser, "show inventory", base_delay=3)
        template = os.path.join(os.environ["NET_TEXTFSM"], "cisco_ios_show_inventory.textfsm")

        try:
            df_serial = parse_with_textfsm(template, output)
            if not df_serial.empty and "SN" in df_serial.columns:
                serial_num = df_serial["SN"].iloc[0]
            else:
                serial_num = None
        except Exception as e:
            print(f"⚠ Error al parsear con TextFSM: {e}")
            serial_num = None

        if not serial_num:
            print("⚠ No se pudo obtener el número de serie. Saltando...")
            return False

        if hostname[1:] != serial_num:
            print(f"⚠ Serie del dispositivo ({serial_num}) ≠ Esperada ({hostname[1:]})")
            return False

        # Comandos de configuración
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
3. Actualizar CSV con estado de puertos
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
    Hostnames = [str(d).strip()[0] + str(s).strip() for d, s in zip(df["Device"], df["Serie"])]
    dispositivos = [(h, u, pas, dom) for u, pas, dom, h in zip(df["User"], df["Password"], df["Ip-domain"], Hostnames)]
    configurados, saltados = [], []
    for idx, (h, u, pas, dom) in enumerate(dispositivos, start=1):
        clear_console()
        print(f"\n➡ Configurando dispositivo {idx}: {h}")
        if configure_device(ser, h, u, pas, dom):
            configurados.append(h)
        else:
            saltados.append(h)
        input("Presione ENTER para continuar...")
    clear_console()
    print("📊 Resumen de configuración:")
    print(f"✅ Configurados ({len(configurados)}): {configurados}")
    print(f"⚠ Saltados ({len(saltados)}): {saltados}")
    input("Presione ENTER para volver al menú...")

def menu_estado_puertos(ser):
    csv_path = r"C:\Users\jessu\OneDrive\Documentos\venv\Data.csv"
    get_ports_status_update_csv(ser, csv_path)
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
            elif opcion == "3":
                menu_estado_puertos(ser)
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
