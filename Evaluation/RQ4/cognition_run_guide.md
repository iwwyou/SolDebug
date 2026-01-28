# Cognition.run 배포 가이드

## 1. 계정 생성
1. https://www.cognition.run 접속
2. "Sign Up" 클릭
3. 이메일로 가입 (무료)

## 2. 실험 업로드

### 필요한 파일들
```
experiment.html    (메인 실험 파일)
problem_1.png
problem_2.png
problem_3.png
problem_4.png
problem_5.png
```

### 업로드 방법
1. Dashboard에서 "New Experiment" 클릭
2. "Upload files" 선택
3. 위 6개 파일을 모두 업로드
4. Main file로 `experiment.html` 선택
5. "Create Experiment" 클릭

## 3. 실험 설정
- **Name**: Program Comprehension Study
- **Description**: Smart contract code comprehension experiment
- **Completion URL**: (선택사항) 완료 후 이동할 URL

## 4. 실험 배포
1. "Publish" 클릭
2. 실험 URL 생성됨 (예: https://cognition.run/task/xxxxx)
3. 이 URL을 참가자에게 공유

## 5. 데이터 확인
1. Dashboard → 해당 실험 클릭
2. "Data" 탭에서 결과 확인
3. CSV로 다운로드 가능

## 6. 무료 플랜 제한
- 참가자 50명까지 무료
- 그 이상 필요시 유료 플랜 또는 자체 호스팅

---

## 로컬 테스트 방법

### Windows
```bash
cd Evaluation/RQ4
python -m http.server 8000
```
브라우저에서 `http://localhost:8000/experiment.html` 접속

### 주의사항
- 로컬에서 파일을 직접 열면 (file://) 이미지 로드가 안 될 수 있음
- 반드시 로컬 서버를 통해 테스트

---

## 데이터 분석

### 주요 데이터 필드
- `rt`: 반응 시간 (밀리초)
- `problem_name`: 문제 이름
- `complexity`: 복잡도
- `correct_answer`: 정답
- `participant_answer`: 참가자 답변
- `is_correct`: 정답 여부

### CSV 다운로드 후 분석
```python
import pandas as pd

df = pd.read_csv('data.csv')

# 정답률
accuracy = df[df['task'] == 'answer'].groupby('problem_name')['is_correct'].mean()

# 평균 응답 시간
rt = df[df['task'] == 'view_problem'].groupby('problem_name')['rt'].mean()
```
