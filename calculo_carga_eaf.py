
import yaml
from gekko import GEKKO
from prettytable import PrettyTable
from reports import print_resultados_carga, print_table_resultados, print_quimica_carga

# Variable global de depuración - cambiar a True para habilitar mensajes de depuración
DEBUG = False


def calcular_adicion_optima(materials_data, alloy_info, colada_peso, colada_quimica):
    """
    Calcula la adición óptima de materiales para ajustar la colada actual a la química final objetivo.
    Considera solo restricciones químicas y de stock.
    @param materials_data: Diccionario de materiales (con química, stock, costo, etc).
    @param alloy_info: Diccionario con los límites de química final ('min', 'max').
    @param colada_peso: Peso actual de la colada en el horno (kg).
    @param colada_quimica: Diccionario con la química medida actual de la colada (porcentaje en peso, ej: {'C': 0.5, 'Mn': 0.8, ...}).
    @return: Modelo GEKKO y variables óptimas de adición.
    """

    materials = list(materials_data.keys())
    elements = list(alloy_info['min'].keys())
    cost = [materials_data[m]['cost'] for m in materials]
    stock = [materials_data[m]['stock'] for m in materials]

    # objeto GEKKO (wrapper optimizador)
    m = GEKKO(remote=False)

    # Valor inicial pequeño para las adiciones y limite de stock en la variable
    x = [m.Var(value=0.001, lb=0, ub=stock[i]) for i in range(len(materials))]

    # Peso total de la colada después de la adición
    total_peso = colada_peso + sum(x)

    # Restricciones químicas (mezcla colada + adición)
    # Química total después de la adición (mezcla ponderada)
    for e in elements:
        min_mix = (colada_quimica.get(e, 0) * colada_peso + sum(x[i]*normalize_chemistry_value(materials_data[materials[i]]['chemistry']['min'].get(e,0)) for i in range(len(materials)))) / total_peso
        max_mix = (colada_quimica.get(e, 0) * colada_peso + sum(x[i]*normalize_chemistry_value(materials_data[materials[i]]['chemistry']['max'].get(e,0)) for i in range(len(materials)))) / total_peso
        
        m.Equation(max_mix <= normalize_chemistry_value(alloy_info['max'][e]))
        m.Equation(min_mix >= normalize_chemistry_value(alloy_info['min'][e]))

        # if max_mix > min_mix para cada elemento no requerimos las dos restricciones de mas abajo
        #m.Equation(max_mix >= normalize_chemistry_value(alloy_info['min'][e]))
        #m.Equation(min_mix <= normalize_chemistry_value(alloy_info['max'][e]))


    # Objetivo: minimizar el costo de la adición
    m.Obj(sum(x[i]*cost[i] for i in range(len(materials))))

    # Resolver
    x = m.solve(disp=True)

    return m, x


def normalize_chemistry_value(value):
    """
    @brief Normaliza los valores de química (convierte a fracción decimal de porcentaje en peso).
    @param value Valor de química desde YAML (porcentaje).
    @return Valor como fracción decimal (0-1).
    """
    if value is None:
        return 0.0
    # All chemistry values in YAML are in percentages, divide by 100
    return value / 100.0

def get_val(var):
    """
    @brief Obtiene el valor de una variable GEKKO.
    @param var Variable GEKKO.
    @return Valor como float.
    """
    v = var.value
    try:
        return v[0]
    except (TypeError, IndexError):
        return v

def solucion_inicial(heat_weight, materials_data):
    """
    @brief Helper para generar una solucion inicial usando una composición tipica de un CM.
    @param heat_weight Peso objetivo total de la carga (kg).
    @return Lista de valores iniciales para las variables de decisión.
    """

    materials = list(materials_data.keys())

    # Composición nominal de carga basada en la práctica de acería
    nominal_composition = {
        'fierro_Primera': 0.2,    # 20%
        'Retornos_CM': 0.35,      # 35%
        'chatarra_CM': 0.44,      # 44%
    }

    # Iniciar con la composición nominal
    initial_x = []
    for i, material in enumerate(materials):
        if material in nominal_composition:
            nominal_amount = nominal_composition[material] * heat_weight
        else:
            # Para materiales que no están en la composición nominal, usar cero
            nominal_amount = 0.0
        initial_x.append(nominal_amount)

    # Normalizar para cumplir la restricción de peso total
    total_weight = sum(initial_x)
    scale_factor = heat_weight / total_weight
    initial_x = [x * scale_factor for x in initial_x]
    return initial_x

def crear_modelelo(materials_data, alloy_info, heat_weight):
    """
    @brief Crea y configura el modelo de optimización.
    @param materials_data Diccionario con la información de los materiales.
    @param alloy_info Diccionario con la información de la carga/aleación (incluye min, max, min_acero_pct, max_returns, etc).
    @param heat_weight Peso objetivo total de la carga (kg).
    @return Modelo GEKKO y lista de variables.
    """
    charge_min = alloy_info['min']
    charge_max = alloy_info['max']
    min_acero_pct = alloy_info.get('min_acero_pct', 0.0)
    max_returns = alloy_info.get('max_returns', None)
    materials = list(materials_data.keys())
    elements = list(charge_min.keys())
    cost = [materials_data[m]['cost'] for m in materials]
    stock = [materials_data[m]['stock'] for m in materials]
    mat_min = [float(str(materials_data[m]['min']).replace('%',''))/100 for m in materials]
    mat_max = [float(str(materials_data[m]['max']).replace('%',''))/100 for m in materials]


    # Buscar una solución inicial factible
    initial_solution = solucion_inicial(heat_weight, materials_data)

    # Crear modelo GEKKO
    m = GEKKO(remote=False)
    x = [m.Var(value=initial_solution[i], lb=0, ub=stock[i]) for i in range(len(materials))]

    # Restricción: peso total
    m.Equation(sum(x) == heat_weight)

    # Restricción: mínimo de materiales tipo "acero" según min_acero_pct
    acero_indices = [i for i, m_name in enumerate(materials) if materials_data[m_name].get('type', '').lower() == 'acero']
    if acero_indices and min_acero_pct > 0:
        m.Equation(sum(x[i] for i in acero_indices) >= min_acero_pct * heat_weight)

    # Restricción: máximo de materiales tipo "returns" según max_returns
    returns_indices = [i for i, m_name in enumerate(materials) if materials_data[m_name].get('type', '').lower() == 'returns']
    if returns_indices and max_returns is not None:
        m.Equation(sum(x[i] for i in returns_indices) <= max_returns * heat_weight)

    # Restricciones de química para los límites mínimo y máximo de los materiales
    for e in elements:
        min_mix = sum(x[i]*normalize_chemistry_value(materials_data[materials[i]]['chemistry']['min'].get(e,0)) for i in range(len(materials)))/heat_weight
        max_mix = sum(x[i]*normalize_chemistry_value(materials_data[materials[i]]['chemistry']['max'].get(e,0)) for i in range(len(materials)))/heat_weight
        m.Equation(min_mix >= normalize_chemistry_value(charge_min[e]))
        m.Equation(min_mix <= normalize_chemistry_value(charge_max[e]))
        m.Equation(max_mix >= normalize_chemistry_value(charge_min[e]))
        m.Equation(max_mix <= normalize_chemistry_value(charge_max[e]))

    # Restricciones de porcentaje para cada material (lineal)
    for i in range(len(materials)):
        m.Equation(x[i]/heat_weight >= mat_min[i])
        m.Equation(x[i]/heat_weight <= mat_max[i])

    # Objetivo: minimizar el costo
    m.Obj(sum(x[i]*cost[i] for i in range(len(materials))))

    return m, x

def calcular_carga(materials_data, alloy_info, charge_weight):
    """
    @brief Resuelve el problema de optimización y retorna el estado y los valores de las variables.
    @param materials_data Diccionario con la información de los materiales.
    @param alloy_info Diccionario con la información de la carga/aleación (incluye min, max, min_acero_pct, max_returns, etc).
    @param charge_weight Peso objetivo total de la carga (kg).
    @return (success_flag, x) donde success_flag es True si es factible, False en caso contrario.
    """

    m, x = crear_modelelo(materials_data, alloy_info, charge_weight)

    try:
        m.solve(disp=False)  # Deshabilitar salida detallada
        if DEBUG:
            print(f"DEBUG - Estado del solver: {m.options.APPSTATUS}")
        return True, x
    except Exception as e:
        if DEBUG:
            print(f"DEBUG - Excepción durante la resolución: {e}")
            print(f"DEBUG - Estado del solver: {m.options.APPSTATUS}")
        # Retornar valores de variables incluso si es infactible
        return False, x

def main():
    # Cargar datos de materiales y objetivos desde YAML
    with open('materials.yaml', 'r') as f:
        materials_data = yaml.safe_load(f)
    with open('alloys.yaml', 'r') as f:
        alloys_data = yaml.safe_load(f)

    # Seleccionar la aleación objetivo
    alloy_charge_info = alloys_data['cm1']['Carga']

    # Definir el peso objetivo de la carga (puede cambiarse)
    heat_weight = 20000  # kg (20 toneladas)

    success, x = calcular_carga(materials_data, alloy_charge_info, heat_weight)

    # Mostrar resultados de la optimización
    if success:
        print("Solución óptima encontrada")
    else:
        print("Error de optimización: No se encontró una solución factible")
        print("Mostrando la mejor solución encontrada (puede violar restricciones)")
        print("Sugerencias:")
        print("1. Verifique los rangos de química en alloys.yaml")
        print("2. Aumente el stock disponible de materiales")
        print("3. Relaje las restricciones de porcentaje mínimo/máximo")

    # Generar reportes para la mejor solución encontrada
    print_resultados_carga(x, materials_data)
    print_table_resultados(x, materials_data, alloy_charge_info)
    print_quimica_carga(x, materials_data, alloy_charge_info)

    # Seleccionar la aleación objetivo y la química final
    final_info = alloys_data['cm1']['Final']

    # Supongamos que la colada actual tiene:
    colada_peso = 12000  # kg
    colada_quimica = {
        'C': 0.30,
        'Mn': 0.30,
        'P': 0.010,
        'S': 0.012,
        'Cr': 1.0,
        'Ni': 0.10,
        'Mo': 0.10,
        'Cu': 0.05,
        'Si': 0.01
    }

    # Calcular adición óptima
    m, x = calcular_adicion_optima(materials_data, final_info, colada_peso, colada_quimica)
    if m.options.APPSTATUS == 1:
        print("Adición óptima encontrada:")
        # Calcular el total de adición y el costo
        materials = list(materials_data.keys())
        cost = [materials_data[m]['cost'] for m in materials]
        total_adicion = sum(get_val(x[i]) for i in range(len(materials)))
        total_cost = sum(get_val(x[i]) * cost[i] for i in range(len(materials)))
        print(f"Total adición: {total_adicion:.1f} kg")
        print(f"Costo total de la adición: ${total_cost:.2f}")
        print_table_resultados(x, materials_data, final_info)
if __name__ == "__main__":
    main()