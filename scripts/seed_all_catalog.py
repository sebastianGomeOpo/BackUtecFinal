"""
Master Seed Script - Ejecuta todos los catálogos en orden
Total: 58 productos nuevos del hogar
"""
import asyncio
import subprocess
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))


async def run_seed_script(script_name: str, part_name: str):
    """Run a seed script and report results"""
    script_path = Path(__file__).parent / script_name
    
    print(f"\n{'='*60}")
    print(f"🚀 Ejecutando: {part_name}")
    print(f"{'='*60}\n")
    
    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            check=True
        )
        print(result.stdout)
        if result.stderr:
            print(f"⚠️  Warnings: {result.stderr}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error ejecutando {part_name}:")
        print(e.stdout)
        print(e.stderr)
        return False


async def main():
    """Execute all seed scripts in sequence"""
    print("\n" + "="*60)
    print("🌱 SEED CATÁLOGO COMPLETO - 58 PRODUCTOS NUEVOS")
    print("="*60)
    
    scripts = [
        ("seed_part1_sala_comedor.py", "Parte 1: Sala y Comedor (15 productos)"),
        ("seed_part2_dormitorio_bano.py", "Parte 2: Dormitorio y Baño (15 productos)"),
        ("seed_part3_cocina_electro.py", "Parte 3: Cocina y Electrodomésticos (15 productos)"),
        ("seed_part4_decoracion_iluminacion.py", "Parte 4: Decoración e Iluminación (13 productos)")
    ]
    
    successful = 0
    failed = 0
    
    for script, description in scripts:
        success = await run_seed_script(script, description)
        if success:
            successful += 1
        else:
            failed += 1
            print(f"⚠️  Continuando con siguiente parte...")
    
    # Final Summary
    print("\n" + "="*60)
    print("📊 RESUMEN FINAL")
    print("="*60)
    print(f"✅ Partes completadas exitosamente: {successful}/4")
    if failed > 0:
        print(f"❌ Partes con errores: {failed}/4")
    
    if successful == 4:
        print("\n🎉 ¡CATÁLOGO COMPLETO CARGADO EXITOSAMENTE!")
        print("\n📦 Productos totales agregados: 58")
        print("📋 Desglose por categoría:")
        print("   • Sala y Comedor: 15 productos")
        print("   • Dormitorio y Baño: 15 productos")
        print("   • Cocina y Electrodomésticos: 15 productos")
        print("   • Decoración e Iluminación: 13 productos")
        print("\n💾 Datos guardados en:")
        print("   • MongoDB: ✅ Productos con stock, precios, categorías")
        print("   • Pinecone: ✅ Embeddings para búsqueda semántica")
        print("\n🤖 El LLM ahora tiene acceso a un catálogo completo y detallado")
        print("   para conversaciones más ricas y ventas efectivas.\n")
    else:
        print("\n⚠️  Algunas partes fallaron. Revisa los logs arriba.")
        print("💡 Puedes ejecutar las partes individualmente si es necesario.")
    
    print("="*60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
