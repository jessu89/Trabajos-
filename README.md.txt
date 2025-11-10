# 🔍 Rastreador de IP en Red Cisco (Python + Netmiko)

Este proyecto permite **rastrear la ubicación física y lógica de una dirección IP dentro de una red Cisco**, mostrando el recorrido entre switches hasta el puerto donde se encuentra conectado el dispositivo final.  

Utiliza **Netmiko** para la conexión SSH con dispositivos Cisco IOS, junto con **regex, pandas y socket** para analizar las tablas ARP, CDP y MAC Address Table.

---

## ⚙️ Funcionalidades

- Conexión automática a switches Cisco mediante SSH.  
- Detección de dirección **MAC asociada a una IP** usando `show ip arp`.  
- Búsqueda de la **interfaz y VLAN** donde aparece esa MAC (`show mac address-table`).  
- Uso de **CDP (Cisco Discovery Protocol)** para seguir la ruta entre switches.  
- Detección del **dispositivo final** cuando ya no hay vecinos CDP.  
- **Exportación automática** de los resultados a un archivo CSV (`ruta_busqueda_ip.csv`).  
- Interfaz de menú simple y limpia en consola.

---

## 🧩 Requisitos

### 📦 Librerías necesarias
Instala las dependencias con:

```bash
pip install netmiko pandas
