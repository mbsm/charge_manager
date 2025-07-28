# Ejemplo básico de optimización de carga EAF usando PuLP
import pulp

# Definición de materiales (nombre, composición química, costo, stock, min, max)
materials = [
    {
        'name': 'MaterialA',
        'composition': {'Fe': 0.95, 'C': 0.02, 'Mn': 0.01},
        'cost': 100,
        'stock': 50,
        'min': 0,
        'max': 50
    },
    {
        'name': 'MaterialB',
        'composition': {'Fe': 0.85, 'C': 0.10, 'Mn': 0.03},
        'cost': 80,
        'stock': 30,
        'min': 5,
        'max': 30
    },
    # Agrega más materiales según tu caso
]

# Objetivo: peso total de la carga (en toneladas)
target_weight = 60

# Rango objetivo para cada elemento químico (porcentaje en la carga final)
chemistry_targets = {
    'Fe': (0.90, 0.96),
    'C': (0.015, 0.025),
    'Mn': (0.008, 0.015)
}

# Crear el problema de optimización
prob = pulp.LpProblem('EAF_Charge_Optimization', pulp.LpMinimize)

# Variables: cantidad de cada material a usar (en toneladas)
material_vars = {
    m['name']: pulp.LpVariable(m['name'], lowBound=m['min'], upBound=min(m['max'], m['stock']))
    for m in materials
}

# Restricción: peso total de la carga
prob += pulp.lpSum(material_vars[m['name']] for m in materials) == target_weight, 'TotalWeight'

# Restricciones de química
for elem, (min_val, max_val) in chemistry_targets.items():
    prob += (
        pulp.lpSum(material_vars[m['name']] * m['composition'].get(elem, 0) for m in materials) >= min_val * target_weight,
        f'{elem}_min'
    )
    prob += (
        pulp.lpSum(material_vars[m['name']] * m['composition'].get(elem, 0) for m in materials) <= max_val * target_weight,
        f'{elem}_max'
    )

# Objetivo: minimizar el costo total
prob += pulp.lpSum(material_vars[m['name']] * m['cost'] for m in materials), 'TotalCost'

# Resolver
prob.solve()

# Mostrar resultados
print('Estado de la solución:', pulp.LpStatus[prob.status])
for m in materials:
    print(f"{m['name']}: {material_vars[m['name']].varValue:.2f} toneladas")
print('Costo total:', pulp.value(prob.objective))
