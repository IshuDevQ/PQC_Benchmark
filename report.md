# Benchmarking Post-Quantum KEMs

## Overview
This project benchmarks post-quantum key encapsulation mechanisms including ML-KEM and NTRU using liboqs.

## Key Findings

### 1. Performance
- ML-KEM-512 showed the fastest key generation and encapsulation times.
- ML-KEM-1024 had higher latency due to increased security parameters.
- NTRU variants showed competitive decapsulation performance.

### 2. Size Tradeoffs
- Public key and ciphertext sizes increased with higher security levels.
- ML-KEM-1024 had the largest footprint.

### 3. Practical Insight
- ML-KEM-512 is suitable for performance-critical applications.
- ML-KEM-1024 is better for high-security scenarios.
- NTRU provides an alternative with different performance characteristics.

## Conclusion
The choice of PQ KEM depends on the tradeoff between security level and performance overhead. ML-KEM offers a balanced standard, while NTRU provides competitive alternatives.