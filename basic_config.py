import os
import sys
import serial
import serial.tools.list_ports
import time
import pandas as pd
import textfsm

# ╔════════════════════════════════════════════════════════════════╗
#   CONFIGURACIÓN AUTOMÁTICA DE NTC-TEMPLATES
# ╚════════════════════════════════════════════════════════════════╝

def setup_ntc_templates():
    """Detecta automáticamente la ruta de ntc_templates y la asigna a NET_TEXTFSM."""
    try:
        import ntc_templates
        templates_path = os.path.join(os.path.dirname(ntc_templates.__file__), "templates")
        if os.path.isdir(templates_path):
            os.environ["NET_TEXTFSM"] = templates_path
            print(f"✅ NET_TEXTFSM detectado: {templates_path}")
        else:
            print("⚠ No se encontró carpeta templates dentro de ntc_templates.")
    except ImportError:
        print("❌ ntc-templates no está instalado. Instálalo con: pip install ntc-templates")
        sys.exit(1)

setup_ntc_templates()

# ╔════════════════════════════════════════════════════════════════╗
#   FUNCIONES DE SERIAL Y COMUNICACIÓN
# ╚════════════════════════════════════════════════════════════════╝

def listar_puertos():
    """Lista los puertos disponibles."""
    return list(serial.tools.list_ports.comports())

def conectar_dispositivo():
    """Conecta al primer puerto disponible."""
    while True:
        puertos = listar_puertos()
        if not puertos:
            print("❌ No se detectaron puertos disponibles.")
            time.sleep(2)
            continue

        for i, p in enumerate(puertos, 1):
            print(f"{i}. {p.device} - {p.description}")

        port = puertos[0].device
        try:
            ser = serial.Serial(port, baudrate=9600, timeout=1)
            time.sleep(2)
            print(f"✅ Conectado a {port}")
            return ser
        except Exception as e:
            print(f"❌ Error al conectar en {port}: {e}")
            time.sleep(2)

def send_command(ser, command, base_delay=2):
    """Envía un comando al router y devuelve la salida limpia."""
    ser.reset_input_buffer()
    ser.write((command + "\r\n").encode())
    time.sleep(base_delay)

    output = ser.read(ser.in_waiting).decode(errors="ignore")
    while True:
        time.sleep(0.5)
        more = ser.read(ser.in_waiting).decode(errors="ignore")
        if not more:
            break
        output += more

    # Limpieza
    lines = output.splitlines()
    clean_lines = [l for l in lines if not l.strip().lower().startswith(command.lower())]
    return "\n".join(clean_lines).strip()

# ╔════════════════════════════════════════════════════════════════╗
#   FUNCIONES DE PARSEO Y CSV
# ╚════════════════════════════════════════════════════════════════╝

def parse_show_ip_interface_brief(raw_output):
    """Parsea show ip interface brief usando TextFSM."""
    template_path = os.path.join(os.environ["NET_TEXTFSM"], "cisco_ios_show_ip_interface_brief.textfsm")
    with open(template_path) as tpl:
        fsm = textfsm.TextFSM(tpl)
        parsed_data = fsm.ParseText(raw_output)

    headers = fsm.header
    return pd.DataFrame(parsed_data, columns=headers)

def obtener_interfaces_y_guardar(ser, csv_path):
    """Ejecuta show ip interface brief, organiza datos en una sola línea y guarda en CSV."""
    router_ip = input("\n🌐 Ingresa la IP del router: ").strip()
    if not router_ip:
        print("⚠ IP inválida.")
        return

    print("\n📡 Obteniendo información de interfaces...")
    send_command(ser, "terminal length 0")
    output = send_command(ser, "show ip interface brief", base_delay=3)

    try:
        df_interfaces = parse_show_ip_interface_brief(output)
        print("\n📋 Interfaces detectadas:")
        print(df_interfaces)

        # Aplanar los datos: poner cada interfaz en columnas horizontales
        row_data = {"Router_IP": router_ip}
        for i, row in df_interfaces.iterrows():
            idx = i + 1
            row_data[f"Int{idx}"] = row["INTERFACE"]
            row_data[f"IP{idx}"] = row["IP-ADDRESS"]
            row_data[f"Status{idx}"] = row["STATUS"]

        # Convertir a DataFrame de una sola fila
        df_row = pd.DataFrame([row_data])

        # Si el CSV ya existe, agregar la nueva fila
        if os.path.exists(csv_path):
            df_csv = pd.read_csv(csv_path)
            df_csv = pd.concat([df_csv, df_row], ignore_index=True)
        else:
            df_csv = df_row

        df_csv.to_csv(csv_path, index=False)
        print(f"\n✅ Datos guardados en una sola línea en: {csv_path}")

    except Exception as e:
        print(f"⚠ Error al parsear interfaces: {e}")
        print("Salida cruda del dispositivo:")
        print(output)

# ╔════════════════════════════════════════════════════════════════╗
#   MENÚ PRINCIPAL
# ╚════════════════════════════════════════════════════════════════╝

def mostrar_menu():
    print("""
╔════════════════════════════════════════════════╗
║                MENÚ PRINCIPAL                  ║
╚════════════════════════════════════════════════╝
1. Obtener interfaces y direcciones IP
0. Salir
""")

# ╔════════════════════════════════════════════════════════════════╗
#   MAIN
# ╚════════════════════════════════════════════════════════════════╝

if __name__ == "__main__":
    ser = conectar_dispositivo()
    csv_path = r"C:\Users\jessu\OneDrive\Documentos\venv\Data.csv"

    while True:
        mostrar_menu()
        opcion = input("Selecciona una opción: ")

        if opcion == "1":
            obtener_interfaces_y_guardar(ser, csv_path)
            input("\nPresiona ENTER para volver al menú...")
        elif opcion == "0":
            print("👋 Saliendo y cerrando conexión...")
            ser.close()
            break
        else:
            print("❌ Opción inválida.")
