import unittest
import pandas as pd
import numpy as np
import sys
sys.path.insert(0, '.')
from engine.profiler import mask, drill_through


class TestMascaras(unittest.TestCase):

    def test_caso_basico(self):
        """Verifica el enmascaramiento carácter a carácter."""
        serie = pd.Series(['Juan C Perez', 'MARIA lopez', None, 'pedro#123'])
        resultado = mask(serie)
        mascaras = resultado['Mascara'].tolist()
        # 'Juan C Perez' → L(J)+l(u)+l(a)+l(n)+s( )+L(C)+s( )+L(P)+l(e)+l(r)+l(e)+l(z)
        self.assertIn('LlllsLsLllll', mascaras)
        # 'MARIA lopez' → 5 mayúsculas + espacio + 5 minúsculas
        self.assertIn('LLLLLslllll', mascaras)
        # 'pedro#123' → 5 minúsculas + # + 3 dígitos
        self.assertIn('lllll#DDD', mascaras)
        self.assertIn('-null-', mascaras)
        self.assertEqual(len(resultado), 4)

    def test_valor_nulo(self):
        """Los nulos deben convertirse a -null-."""
        serie = pd.Series([None, np.nan, float('nan')])
        resultado = mask(serie)
        self.assertEqual(len(resultado), 1)
        self.assertEqual(resultado.iloc[0]['Mascara'], '-null-')
        self.assertEqual(resultado.iloc[0]['Count'], 3)

    def test_caracteres_especiales(self):
        """Los caracteres especiales se mantienen tal cual."""
        serie = pd.Series(['test@email.com', 'otro@email.com'])
        resultado = mask(serie)
        self.assertEqual(len(resultado), 1)
        self.assertEqual(resultado.iloc[0]['Mascara'], 'llll@lllll.lll')

    def test_tipo_dato_incorrecto(self):
        """Números enteros deben convertirse a string antes de enmascarar."""
        serie = pd.Series([123, 456, 789])
        resultado = mask(serie)
        self.assertIn('DDD', resultado['Mascara'].tolist())

    def test_porcentaje_suma_100(self):
        """Los porcentajes deben sumar 100."""
        serie = pd.Series(['Hola', 'mundo', 'test', None])
        resultado = mask(serie)
        self.assertAlmostEqual(resultado['Porcentaje'].sum(), 100.0, places=1)

    def test_drill_through(self):
        """drill_through retorna solo las filas con la máscara especificada."""
        df = pd.DataFrame({
            'id': [1, 2, 3, 4],
            'nombre': ['Juan Perez', 'MARIA LOPEZ', 'carlos', None]
        })
        resultado = drill_through(df, 'nombre', 'LlllsLllll')
        self.assertEqual(len(resultado), 1)
        self.assertEqual(resultado.iloc[0]['id'], 1)

    def test_ordenado_por_count(self):
        """El resultado debe estar ordenado de mayor a menor por Count."""
        serie = pd.Series(['Hola', 'Mundo', 'TEST', 'TEST', 'TEST'])
        resultado = mask(serie)
        counts = resultado['Count'].tolist()
        self.assertEqual(counts, sorted(counts, reverse=True))

    def test_drill_through_nulo(self):
        """drill_through funciona correctamente con la máscara '-null-'."""
        df = pd.DataFrame({
            'id': [1, 2, 3],
            'col': ['Hola', None, 'Mundo']
        })
        resultado = drill_through(df, 'col', '-null-')
        self.assertEqual(len(resultado), 1)
        self.assertEqual(resultado.iloc[0]['id'], 2)

    def test_drill_through_sin_resultados(self):
        """drill_through retorna DataFrame vacío si no hay coincidencias."""
        df = pd.DataFrame({'id': [1, 2], 'col': ['Hola', 'Mundo']})
        resultado = drill_through(df, 'col', 'XXXX')
        self.assertEqual(len(resultado), 0)

    def test_mascara_digitos(self):
        """Dígitos se mapean a D."""
        serie = pd.Series(['12345', '67890'])
        resultado = mask(serie)
        self.assertEqual(resultado.iloc[0]['Mascara'], 'DDDDD')
        self.assertEqual(resultado.iloc[0]['Count'], 2)


if __name__ == '__main__':
    unittest.main(verbosity=2)
