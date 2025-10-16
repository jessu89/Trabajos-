#!/usr/bin/env python3
"""Autor: Ing. Fernndo + Vane ⚡
Descripción:
    Script que pregunta una IP de dispositivo (host o switch)
    y busca en los switches definidos a qué puerto y switch está conectado.
Requiere:
    pip install netmiko pandas
"""

from netmiko import ConnectHandler
import re
import pandas as pd
import os


# ========================================================
# CONFIGURA AQUÍ TUS SWITCHES
# ========================================================
SWITCHES = [
    {
        "device_type": "cisco_ios",
        "host": "192.168.1.1",
        "username": "cisco",
        "password": "cisco99",
    },
    # Puedes agregar más switches si tienes varios
    # {"device_type": "cisco_ios", "host": "192.168.1.", "username": "admin", "password": "cisco"},
]


# ========================================================
# FUNCIONES AUXILIARES
# ========================================================

def limpiar():
    os.system("cls" if os.name == "nt" else "clear")


def obtener_mac_por_ip(conn, ip):
    """Ejecuta 'show ip arp' y busca la MAC asociada a una IP."""
    output = conn.send_command("show ip arp", use_textfsm=False)
    for line in output.splitlines():
        if ip in line:
            # Ejemplo de línea: Internet  192.168.1.10  0   0011.2233.4455  ARPA  Vlan10
            m = re.search(rf"{ip}\s+\S+\s+([\w\.]+)\s+ARPA", line)
            if m:
                return m.group(1).replace('.', '').lower()
    return None


def normalizar_mac(mac_raw):
    """Convierte una MAC 001122334455 o 0011.2233.4455 a formato estándar 00:11:22:33:44:55"""
    mac = mac_raw.replace('.', '').replace(':', '').replace('-', '').lower()
    if len(mac) == 12:
        return ':'.join(mac[i:i+2] for i in range(0, 12, 2))
    return mac_raw


def buscar_en_switch(sw, ip_buscada):
    """
    Busca la IP en el switch, correlaciona con su MAC y puerto.
    Retorna dict con resultados o None.
    """
    print(f"\n🔗 Conectando al switch {sw['host']} ...")
    conn = ConnectHandler(**sw)
    hostname = conn.find_prompt().replace("#", "").strip()

    # Paso 1: Buscar la MAC asociada a la IP
    mac_raw = obtener_mac_por_ip(conn, ip_buscada)
    if not mac_raw:
        print(f"⚠️  No se encontró la IP {ip_buscada} en el ARP de {hostname}")
        conn.disconnect()
        return None

    mac_norm = normalizar_mac(mac_raw)
    print(f"✅ IP {ip_buscada} → MAC {mac_norm}")

    # Paso 2: Buscar la MAC en la tabla de direcciones
    output = conn.send_command("show mac address-table", use_textfsm=False)
    for line in output.splitlines():
        if mac_raw[:4] in line or mac_norm.replace(':', '')[:4] in line:
            m = re.search(r"(?P<vlan>\d+)\s+(?P<mac>[0-9a-fA-F\.:-]{11,})\s+\S+\s+(?P<intf>\S+)", line)
            if m:
                interface = m.group("intf")
                conn.disconnect()
                return {
                    "sw_name": hostname,
                    "ip_sw": sw["host"],
                    "puerto_device": interface,
                    "mac_device": mac_norm,
                    "ip_device": ip_buscada,
                }

    conn.disconnect()
    return None


# ========================================================
# MENÚ PRINCIPAL
# ========================================================

def menu():
    while True:
        limpiar()
        print("="*55)
        print("🔍  BUSCADOR DE DISPOSITIVO POR IP (via SSH + CDP/ARP/MAC)")
        print("="*55)
        print("1️⃣  Buscar IP en switches")
        print("2️⃣  Salir")
        print("="*55)

        opcion = input("Selecciona una opción: ").strip()

        if opcion == "1":
            ip_buscar = input("\nIngresa la IP del dispositivo a buscar: ").strip()
            resultados = []

            for sw in SWITCHES:
                try:
                    res = buscar_en_switch(sw, ip_buscar)
                    if res:
                        resultados.append(res)
                        break  # dejamos de buscar al encontrarlo
                except Exception as e:
                    print(f"❌ Error con {sw['host']}: {e}")

            if resultados:
                df = pd.DataFrame(resultados)
                print("\n=== RESULTADO ENCONTRADO ===")
                print(df.to_string(index=False))
                df.to_csv("resultado_busqueda_ip.csv", index=False)
                print("\n📄 Guardado en: resultado_busqueda_ip.csv")
            else:
                print(f"\n⚠️ No se encontró la IP {ip_buscar} en ninguno de los switches.")

            input("\nPresiona Enter para continuar...")

        elif opcion == "2":
            print("\n👋 Saliendo del programa... ¡Nos vemos, ingeniero!")
            break

        else:
            print("\n⚠️ Opción no válida.")
            input("\nPresiona Enter para continuar...")


# ========================================================
# EJECUCIÓN
# ========================================================
if __name__ == "__main__":
    menu()
