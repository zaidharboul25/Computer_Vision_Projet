#!/usr/bin/env python
"""
Diagnostic du matériel GPU et de la configuration PyTorch / CUDA.
Usage:
    python backend/scripts/check_gpu.py
"""
import sys


def check_gpu() -> bool:
    print("=" * 60)
    print(" WeaveGuard AI - Diagnostic GPU / CUDA / PyTorch")
    print("=" * 60)

    try:
        import torch
    except ImportError:
        print("[ERREUR] PyTorch n'est pas installé dans l'environnement courant.")
        return False

    print(f"Version PyTorch       : {torch.__version__}")
    cuda_available = torch.cuda.is_available()
    print(f"CUDA disponible (torch): {cuda_available}")

    if not cuda_available:
        print("\n[INFO] CUDA n'est pas disponible pour cet interpréteur PyTorch.")
        print("       (La roue PyTorch installée est soit une version CPU, soit")
        print("        les pilotes / bibliothèques CUDA ne sont pas accessibles).")
        print("       Le backend WeaveGuard AI basculera en mode CPU.")
        print("-" * 60)
        return True

    # Si CUDA est disponible
    device_count = torch.cuda.device_count()
    print(f"Nombre de GPU CUDA    : {device_count}")

    if hasattr(torch.cuda, "get_arch_list"):
        archs = torch.cuda.get_arch_list()
        print(f"Architectures CUDA    : {', '.join(archs)}")
        has_sm61 = any("6.1" in a or "sm_61" in a for a in archs)
        print(f"Support Pascal sm_61  : {'OUI' if has_sm61 else 'NON / Inconnu'}")

    for idx in range(device_count):
        prop = torch.cuda.get_device_properties(idx)
        print(f"\n[GPU {idx}] : {prop.name}")
        print(f"  - Compute Capability : {prop.major}.{prop.minor}")
        total_vram_mb = prop.total_memory / (1024 ** 2)
        print(f"  - VRAM Totale        : {total_vram_mb:.0f} Mo ({total_vram_mb / 1024:.2f} Go)")
        
        # VRAM actuelle
        allocated_mb = torch.cuda.memory_allocated(idx) / (1024 ** 2)
        reserved_mb = torch.cuda.memory_reserved(idx) / (1024 ** 2)
        print(f"  - VRAM Allouée       : {allocated_mb:.1f} Mo")
        print(f"  - VRAM Réservée      : {reserved_mb:.1f} Mo")

    # Petit test réel sur GPU
    print("\n--- Test d'opération réelle sur GPU ---")
    try:
        t0 = torch.randn(256, 256, device="cuda")
        t1 = t0 @ t0
        torch.cuda.synchronize()
        print(f"[SUCCÈS] Multiplication de matrices (256x256) effectuée sur CUDA.")
        print(f"         Valeur trace : {t1.trace().item():.4f}")
        torch.cuda.empty_cache()
    except Exception as e:
        print(f"[ÉCHEC] L'opération sur GPU a échoué : {e}")
        return False

    print("=" * 60)
    return True


if __name__ == "__main__":
    ok = check_gpu()
    sys.exit(0 if ok else 1)

