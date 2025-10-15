# Remix Debugger Latency Benchmark Guide

이 가이드는 Remix IDE의 디버깅 latency를 자동으로 측정하고, 회귀 모델을 통해 전체 데이터셋의 latency를 예측하는 방법을 설명합니다.

## 목차
1. [개요](#개요)
2. [설치](#설치)
3. [워크플로우](#워크플로우)
4. [스크립트 설명](#스크립트-설명)
5. [결과 분석](#결과-분석)

---

## 개요

### 문제점
- 30개의 컨트랙트를 모두 수기로 Remix에서 테스트하기에는 시간이 너무 오래 걸림
- State Slots 설정이 필요한 경우 디버깅 시간이 비례해서 증가함
- ByteOp(실행된 opcode 수)가 측정되지 않음

### 해결책
1. **Selenium 자동화**: Remix IDE를 자동으로 조작하여 latency 측정
2. **performance.now() API**: 브라우저의 고정밀 타이머로 정확한 시간 측정
3. **회귀 모델**: 일부만 측정하고 나머지는 예측
   - `Latency = f(State Slots, ByteOp, Annotation Targets)`

---

## 설치

### 1. Python 패키지 설치
```bash
pip install selenium pandas openpyxl scikit-learn matplotlib
```

### 2. ChromeDriver 설치
```bash
pip install webdriver-manager
```

또는 수동으로 [ChromeDriver](https://chromedriver.chromium.org/)를 다운로드하여 PATH에 추가

### 3. 프로젝트 구조 확인
```
SolDebug/
├── dataset/
│   ├── contraction/          # 축약된 컨트랙트 파일들 (*_c.sol)
│   ├── evaluation_Dataset.xlsx
│   └── ...
├── remix_benchmark.py         # Remix 자동화 벤치마크
├── measure_byteop.py          # ByteOp 측정 유틸리티
├── latency_model.py           # 회귀 모델 구축 및 예측
└── REMIX_BENCHMARK_README.md  # 이 파일
```

---

## 워크플로우

### Phase 1: ByteOp 측정 (선택사항이지만 권장)

ByteOp는 함수 실행 시 거치는 EVM opcode의 총 개수입니다.

#### 옵션 A: 빠른 추정 (부정확)
```bash
python measure_byteop.py --estimate
```
- 함수의 라인 수를 기반으로 대략적인 ByteOp 추정
- 실제 실행 경로와 다를 수 있음 (조건문, 반복문 등)

#### 옵션 B: 정확한 측정 (권장, 시간 소요)
```bash
python measure_byteop.py
```
- Remix 디버거에서 실제 실행된 opcode 수를 측정
- 약 15-20분 소요 (30개 × ~30초)
- `evaluation_Dataset_with_byteop.xlsx` 생성

---

### Phase 2: 샘플 벤치마킹

**전체 30개를 모두 측정하지 않고**, 대표적인 샘플만 측정합니다.

#### 전략: 다양성 있는 샘플링
- **작은 컨트랙트** (State Slots < 3, ByteOp < 100): 2-3개
- **중간 컨트랙트** (State Slots 3-7, ByteOp 100-300): 3-4개
- **큰 컨트랙트** (State Slots > 7, ByteOp > 300): 2-3개

총 **8-10개 샘플**이면 충분합니다!

```bash
python remix_benchmark.py
```

스크립트 내에서 `sample_size` 조정:
```python
# remix_benchmark.py 맨 아래
if __name__ == "__main__":
    # 8개 샘플, 3회 반복 측정
    results = run_benchmark_suite(num_runs=3, sample_size=8)
```

#### 측정되는 시간들
1. **setup_time_ms**: 파일 생성 시간
2. **compile_time_ms**: 컴파일 시간
3. **deploy_time_ms**: 배포 시간
4. **state_slot_setup_time_ms**: 상태변수 설정 시간 (State Slots 개수에 비례)
5. **execution_time_ms**: 함수 실행 시간
6. **debug_open_time_ms**: 디버거 열기 시간 ⭐
7. **jump_to_end_time_ms**: 마지막 스텝으로 이동 시간 ⭐
8. **variable_extraction_time_ms**: 변수 값 추출 시간 ⭐
9. **pure_debug_time_ms**: 6+7+8 (실제 디버깅 경험 시간) ⭐⭐
10. **total_time_ms**: 전체 시간

**핵심 메트릭: `pure_debug_time_ms`** - 사용자가 체감하는 실제 디버깅 시간

---

### Phase 3: 회귀 모델 구축 및 예측

샘플 데이터로 모델을 학습하고, 나머지 컨트랙트의 latency를 예측합니다.

```bash
python latency_model.py
```

#### 출력
1. **Linear 모델**
   ```
   Latency = α + β₁×StateSlots + β₂×ByteOp + β₃×AnnotationTargets
   ```

   예시:
   ```
   Intercept: 245.32ms
   Coefficients:
     State Slots:        +15.4ms per slot
     ByteOp Count:       +0.25ms per op
     Annotation Targets: +8.7ms per target
   ```

2. **Polynomial 모델** (더 복잡한 관계 포착)

3. **성능 지표**
   - **R² Score**: 모델 설명력 (0.8 이상이면 좋음)
   - **RMSE**: 평균 오차 (ms 단위)
   - **MAPE**: 평균 퍼센트 오차

4. **시각화**: `latency_model_performance.png`
   - Predicted vs Actual
   - Residual plot
   - Feature importance
   - Error distribution

5. **전체 예측**: `predicted_latencies.csv`
   - 30개 모든 컨트랙트의 예측 latency

---

## 스크립트 설명

### 1. `remix_benchmark.py`

Remix IDE를 Selenium으로 자동화하여 디버깅 latency를 측정합니다.

**주요 기능:**
- `RemixBenchmark` 클래스: Remix IDE 자동화
  - `_create_contract_file()`: 컨트랙트 업로드
  - `_compile_contract()`: 컴파일
  - `_deploy_contract()`: JavaScript VM에 배포
  - `_set_state_slots()`: 상태변수 설정 (중요!)
  - `_execute_function()`: 함수 실행
  - `_open_debugger()`: 디버거 열기 (performance.now() 사용)
  - `_get_total_steps()`: ByteOp 카운트 추출
  - `_jump_to_end()`: 마지막 스텝으로 이동 (performance.now() 사용)
  - `_extract_variables()`: 변수 값 추출 (performance.now() 사용)

**핵심 측정 기법:**
```python
# JavaScript performance.now() API 활용
self.driver.execute_script("""
    window.debugStartTime = performance.now();
""")

# ... 작업 수행 ...

debug_time = self.driver.execute_script("""
    return performance.now() - window.debugStartTime;
""")
```

**결과 파일:**
- `remix_benchmark_results.csv`: 모든 측정 결과
- `remix_benchmark_results.json`: JSON 형식

---

### 2. `measure_byteop.py`

ByteOp (실행된 EVM opcode 수)를 측정하거나 추정합니다.

**두 가지 모드:**

#### 추정 모드 (빠름, 부정확)
```bash
python measure_byteop.py --estimate
```
- 함수 라인 수 × 6 opcodes/line (경험적 상수)
- 결과: `byteop_estimates.csv`

#### 측정 모드 (느림, 정확)
```bash
python measure_byteop.py
```
- Remix 디버거 슬라이더의 `max` 속성 읽기
- 실제 실행 경로의 opcode 수
- 결과: `evaluation_Dataset_with_byteop.xlsx`

**ByteOp가 중요한 이유:**
- ByteOp가 많을수록 디버거가 더 많은 스텝을 처리해야 함
- 디버깅 latency와 강한 선형 관계

---

### 3. `latency_model.py`

회귀 모델을 구축하여 미측정 컨트랙트의 latency를 예측합니다.

**주요 기능:**
- `LatencyModel` 클래스
  - Linear Regression
  - Polynomial Regression (degree=2)

- `build_model_from_results()`: 벤치마크 결과로 모델 학습

- `predict_all_contracts()`: 전체 데이터셋 예측

- `visualize_model_performance()`: 모델 성능 시각화

**모델 선택:**
- Linear와 Polynomial 모두 학습
- R² score가 높은 모델 자동 선택

**예측 워크플로우:**
```
샘플 데이터 (8-10개) → 모델 학습 → 나머지 (20-22개) 예측
```

---

## 결과 분석

### 예상 결과 해석

#### 1. State Slots의 영향
State Slots가 많을수록:
- 함수 실행 전 상태변수를 설정하는 시간 증가
- 디버거가 더 많은 스토리지 상태를 추적해야 함

**예상 계수:** +10~20ms per slot

#### 2. ByteOp의 영향
ByteOp가 많을수록:
- 디버거가 더 많은 스텝을 처리
- 변수 추출 시 더 많은 스택/메모리 분석

**예상 계수:** +0.1~0.5ms per opcode

#### 3. Annotation Targets의 영향
추적할 변수가 많을수록:
- 변수 값 추출 시간 증가
- UI 렌더링 시간 증가

**예상 계수:** +5~15ms per target

---

### 모델 신뢰도 평가

#### 좋은 모델 (사용 가능)
- **R² > 0.75**: 모델이 75% 이상의 분산 설명
- **MAPE < 20%**: 평균 오차가 20% 미만
- **Residual plot이 random**: 체계적 편향 없음

#### 나쁜 모델 (샘플 추가 필요)
- **R² < 0.5**: 설명력 부족
- **MAPE > 30%**: 오차가 너무 큼
- **Residual plot에 패턴**: 모델이 특정 관계를 놓침

**개선 방법:**
1. 샘플 크기 증가 (8→12개)
2. 다양한 범위의 컨트랙트 추가 (작은 것, 중간, 큰 것)
3. Polynomial 모델 사용

---

### Remix vs Your Tool 비교

최종 비교표:

| Contract | State Slots | ByteOp | Remix Latency (predicted) | Your Tool Latency | Speedup |
|----------|-------------|--------|---------------------------|-------------------|---------|
| AloeBlend | 2 | 245 | 312ms | 45ms | **6.9x** |
| ATIDStaking | 7 | 562 | 478ms | 89ms | **5.4x** |
| ... | ... | ... | ... | ... | ... |
| **Average** | **4.3** | **327** | **385ms** | **62ms** | **6.2x** |

---

## 주의사항

### Remix 자동화 시 주의점

1. **네트워크 속도**: Remix가 웹 기반이므로 인터넷 속도 영향
   - 로컬 네트워크에서 테스트 권장

2. **브라우저 성능**: Chrome이 백그라운드 프로세스를 많이 사용
   - 테스트 중 다른 작업 최소화

3. **DOM 변화**: Remix UI가 업데이트되면 selector 변경 가능
   - CSS selector가 작동하지 않으면 업데이트 필요

4. **타임아웃**: 큰 컨트랙트는 컴파일/실행 시간이 오래 걸림
   - `WebDriverWait` timeout 조정 필요

### State Slots 설정 문제

현재 구현은 **public 변수**나 **setter 함수**를 통한 설정을 가정합니다.

만약 private 변수거나 복잡한 초기화가 필요한 경우:
- Constructor에서 초기화하도록 컨트랙트 수정
- 또는 테스트용 setter 함수 추가

---

## FAQ

### Q1: 왜 30개를 모두 측정하지 않나요?
**A:** 회귀 모델을 사용하면 8-10개 샘플만으로도 전체를 예측할 수 있습니다.
- 측정 시간 절약: 15분 → 5분
- 모델의 R²가 0.8 이상이면 예측 신뢰도 높음

### Q2: ByteOp를 꼭 측정해야 하나요?
**A:** 권장합니다. ByteOp는 latency와 가장 강한 상관관계를 가집니다.
- 추정만 해도 어느 정도 작동하지만, 정확도가 떨어짐
- 한 번만 측정하면 재사용 가능

### Q3: Solidity Debugger Pro도 같은 방법으로 측정하나요?
**A:** 유사하지만 VS Code Extension이므로:
- VS Code의 Debug Adapter Protocol을 사용
- `launch.json` 설정으로 자동화
- Breakpoint에서 변수 읽기는 `vscode.debug.activeDebugSession.customRequest()` 사용

별도 스크립트 필요 (추후 작성 가능)

### Q4: 모델의 R²가 낮게 나왔어요
**A:** 다음을 확인하세요:
1. 샘플 다양성: 작은/중간/큰 컨트랙트를 고르게 샘플링했는지
2. ByteOp 정확성: 추정이 아닌 실제 측정값 사용
3. 이상치: 특정 컨트랙트가 비정상적으로 느린지 확인
4. 샘플 크기: 8개 → 12개로 증가

---

## 다음 단계

1. **Solidity Debugger Pro 측정 스크립트 작성**
2. **비교 시각화 대시보드**
3. **논문/발표 자료용 그래프 생성**

---

## 라이센스 및 문의

이 스크립트는 연구 목적으로 작성되었습니다.

문제가 있거나 개선 사항이 있으면 이슈를 남겨주세요.
