import yaml
from gekko import GEKKO

# Cargar datos de materiales y objetivos desde YAML
with open('materials.yaml', 'r') as f:
    materials_data = yaml.safe_load(f)
with open('alloys.yaml', 'r') as f:
    alloys_data = yaml.safe_load(f)

# Parámetros del problema
charge_limits = alloys_data['cm1']['charge']
charge_min = charge_limits['min']
charge_max = charge_limits['max']

materials = list(materials_data.keys())
elements = list(charge_min.keys())

cost = [materials_data[m]['cost'] for m in materials]
stock = [materials_data[m]['stock'] for m in materials]
mat_min = [float(str(materials_data[m]['min']).replace('%',''))/100 for m in materials]
mat_max = [float(str(materials_data[m]['max']).replace('%',''))/100 for m in materials]

# Peso objetivo de la carga (puedes cambiarlo)
heat_weight = 20  # toneladas

# Crear modelo gekko
m = GEKKO(remote=False)
x = [m.Var(value=heat_weight/len(materials), lb=0, ub=stock[i]) for i in range(len(materials))]

# Restricción: peso total
m.Equation(sum(x) == heat_weight)


# Restricciones de química usando la mezcla mínima y máxima
for j, e in enumerate(elements):
    # química mínima de la mezcla
    min_mix = sum(x[i]*materials_data[materials[i]]['chemestry']['min'].get(e,0) for i in range(len(materials)))/heat_weight
    # química máxima de la mezcla
    max_mix = sum(x[i]*materials_data[materials[i]]['chemestry']['max'].get(e,0) for i in range(len(materials)))/heat_weight
    # Ambas mezclas deben estar dentro del rango objetivo
    m.Equation(min_mix >= charge_min[e])
    m.Equation(min_mix <= charge_max[e])
    m.Equation(max_mix >= charge_min[e])
    m.Equation(max_mix <= charge_max[e])

# Restricciones de porcentaje de cada material (ahora lineales)
for i in range(len(materials)):
    m.Equation(x[i]/heat_weight >= mat_min[i])
    m.Equation(x[i]/heat_weight <= mat_max[i])

# Objetivo: minimizar el costo
m.Obj(sum(x[i]*cost[i] for i in range(len(materials))))

def get_val(var):
    v = var.value
    try:
        return v[0]
    except (TypeError, IndexError):
        return v

m.solve(disp=True)

# Calcular la química resultante de la solución
solution_chemistry_min = {}
solution_chemistry_max = {}
for j, e in enumerate(elements):
    solution_chemistry_min[e] = sum(x[i].value[0]*materials_data[materials[i]]['chemestry']['min'].get(e,0) for i in range(len(materials)))/heat_weight
    solution_chemistry_max[e] = sum(x[i].value[0]*materials_data[materials[i]]['chemestry']['max'].get(e,0) for i in range(len(materials)))/heat_weight

# Imprimir tabla de química
print('\nTabla de química (porcentaje en la carga):')
header = '| Elemento | Especificación Mínima | Estimación Mínima | Estimación Máxima | Especificación Máxima |'
print(header)
print('|' + '-'*(len(header)-2) + '|')
for e in elements:
    print(f"| {e:8} | {charge_min[e]:22.3f} | {solution_chemistry_min[e]:16.3f} | {solution_chemistry_max[e]:16.3f} | {charge_max[e]:22.3f} |")

print('\nCarga óptima:')
for i, mat in enumerate(materials):
    print(f"{mat}: {get_val(x[i]):.2f} toneladas")
print('Peso total de la carga:', sum(get_val(x[i]) for i in range(len(materials))))
print('Costo total:', sum(get_val(x[i])*cost[i] for i in range(len(materials))))

print('\nTabla de materiales:')
header_mat = '| Material         | Mínimo    | Valor     | Máximo    | Costo   |'
print(header_mat)
print('|' + '-'*(len(header_mat)-2) + '|')
for i, mat in enumerate(materials):
    min_val = mat_min[i]*heat_weight
    val = get_val(x[i])
    max_val = mat_max[i]*heat_weight
    print(f"| {mat:16} | {min_val:9.2f} | {val:9.2f} | {max_val:9.2f} | {cost[i]:7.2f} |")
