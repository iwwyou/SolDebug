"""
3D Surface Visualization - Connecting points with surfaces/meshes
"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from scipy.interpolate import griddata

def load_data():
    """Load benchmark data"""
    df = pd.read_csv('Evaluation/soldebug_benchmark_results_seconds.csv')
    df = df[df['Remix_PureDebug_s'] != 'N/A'].copy()
    df['ByteOp_Count'] = pd.to_numeric(df['ByteOp_Count'], errors='coerce')
    df['SolQDebug_Latency_s'] = pd.to_numeric(df['SolQDebug_Latency_s'], errors='coerce')
    df['Remix_PureDebug_s'] = pd.to_numeric(df['Remix_PureDebug_s'], errors='coerce')
    df = df.dropna(subset=['ByteOp_Count', 'SolQDebug_Latency_s', 'Remix_PureDebug_s'])
    return df

def create_contract_ribbons(df, save_path='3d_benchmark_ribbons.png'):
    """
    각 컨트랙트를 리본(띠) 형태로 표현
    Input range별 포인트들을 사각형 면으로 연결
    """
    fig = plt.figure(figsize=(16, 12))
    ax = fig.add_subplot(111, projection='3d')

    contracts = df['Contract'].unique()

    for i, contract in enumerate(contracts):
        contract_df = df[df['Contract'] == contract].sort_values('Input_Range')

        if len(contract_df) < 2:
            continue

        x = contract_df['ByteOp_Count'].values
        y = contract_df['Input_Range'].values
        z_solq = contract_df['SolQDebug_Latency_s'].values
        z_remix = contract_df['Remix_PureDebug_s'].values

        # SolQDebug: 파란색 리본
        for j in range(len(x) - 1):
            # 사각형 면 생성 (약간의 폭을 주기 위해 x 좌표를 살짝 이동)
            verts_solq = [
                [x[j] - 5, y[j], z_solq[j]],
                [x[j] + 5, y[j], z_solq[j]],
                [x[j+1] + 5, y[j+1], z_solq[j+1]],
                [x[j+1] - 5, y[j+1], z_solq[j+1]]
            ]
            poly_solq = Poly3DCollection([verts_solq], alpha=0.4,
                                         facecolor='#1f77b4', edgecolor='#0d5a8a', linewidth=0.5)
            ax.add_collection3d(poly_solq)

            # Remix: 오렌지색 리본
            verts_remix = [
                [x[j] - 5, y[j], z_remix[j]],
                [x[j] + 5, y[j], z_remix[j]],
                [x[j+1] + 5, y[j+1], z_remix[j+1]],
                [x[j+1] - 5, y[j+1], z_remix[j+1]]
            ]
            poly_remix = Poly3DCollection([verts_remix], alpha=0.4,
                                         facecolor='#ff7f0e', edgecolor='#cc6600', linewidth=0.5)
            ax.add_collection3d(poly_remix)

        # 포인트 마커 추가
        ax.scatter(x, y, z_solq, c='#1f77b4', marker='o', s=20, alpha=0.8, edgecolors='black', linewidth=0.3)
        ax.scatter(x, y, z_remix, c='#ff7f0e', marker='^', s=20, alpha=0.8, edgecolors='black', linewidth=0.3)

    # 범위 설정
    ax.set_xlim(df['ByteOp_Count'].min() - 50, df['ByteOp_Count'].max() + 50)
    ax.set_ylim(0, 10)
    ax.set_zlim(0, df['Remix_PureDebug_s'].max() * 1.1)

    # Labels
    ax.set_xlabel('ByteOp Count', fontsize=12, fontweight='bold')
    ax.set_ylabel('Input Range', fontsize=12, fontweight='bold')
    ax.set_zlabel('Latency (seconds)', fontsize=12, fontweight='bold')
    ax.set_title('3D Benchmark with Ribbon Surfaces\n(Each Contract Connected by Bands)',
                 fontsize=14, fontweight='bold', pad=20)

    # Custom legend
    from matplotlib.lines import Line2D
    legend_elements = [
        Line2D([0], [0], marker='o', color='w', label='SolQDebug',
               markerfacecolor='#1f77b4', markersize=10, markeredgecolor='black'),
        Line2D([0], [0], marker='^', color='w', label='Remix Pure Debug',
               markerfacecolor='#ff7f0e', markersize=10, markeredgecolor='black')
    ]
    ax.legend(handles=legend_elements, loc='upper left', fontsize=11)

    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"Saved ribbon plot to {save_path}")
    plt.close()

def create_interpolated_surface(df, save_path='3d_benchmark_surface.png'):
    """
    보간된 표면 생성 (smooth surface)
    """
    fig = plt.figure(figsize=(18, 8))

    # Subplot 1: SolQDebug
    ax1 = fig.add_subplot(121, projection='3d')

    x = df['ByteOp_Count'].values
    y = df['Input_Range'].values
    z_solq = df['SolQDebug_Latency_s'].values

    # 그리드 생성
    xi = np.linspace(x.min(), x.max(), 50)
    yi = np.linspace(y.min(), y.max(), 20)
    xi, yi = np.meshgrid(xi, yi)

    # 보간
    zi_solq = griddata((x, y), z_solq, (xi, yi), method='cubic', fill_value=0)

    # Surface plot
    surf1 = ax1.plot_surface(xi, yi, zi_solq, cmap='Blues', alpha=0.7,
                             edgecolor='none', antialiased=True)

    # 원본 데이터 포인트 표시
    ax1.scatter(x, y, z_solq, c='darkblue', marker='o', s=30, alpha=0.9,
                edgecolors='black', linewidth=0.5, zorder=10)

    ax1.set_xlabel('ByteOp Count', fontsize=11, fontweight='bold')
    ax1.set_ylabel('Input Range', fontsize=11, fontweight='bold')
    ax1.set_zlabel('Latency (s)', fontsize=11, fontweight='bold')
    ax1.set_title('SolQDebug - Interpolated Surface', fontsize=13, fontweight='bold', pad=15)
    ax1.grid(True, alpha=0.3)
    fig.colorbar(surf1, ax=ax1, shrink=0.5, aspect=5, pad=0.1)

    # Subplot 2: Remix
    ax2 = fig.add_subplot(122, projection='3d')

    z_remix = df['Remix_PureDebug_s'].values
    zi_remix = griddata((x, y), z_remix, (xi, yi), method='cubic', fill_value=0)

    surf2 = ax2.plot_surface(xi, yi, zi_remix, cmap='Oranges', alpha=0.7,
                             edgecolor='none', antialiased=True)

    ax2.scatter(x, y, z_remix, c='darkorange', marker='^', s=30, alpha=0.9,
                edgecolors='black', linewidth=0.5, zorder=10)

    ax2.set_xlabel('ByteOp Count', fontsize=11, fontweight='bold')
    ax2.set_ylabel('Input Range', fontsize=11, fontweight='bold')
    ax2.set_zlabel('Latency (s)', fontsize=11, fontweight='bold')
    ax2.set_title('Remix Pure Debug - Interpolated Surface', fontsize=13, fontweight='bold', pad=15)
    ax2.grid(True, alpha=0.3)
    fig.colorbar(surf2, ax=ax2, shrink=0.5, aspect=5, pad=0.1)

    # 동일한 viewing angle
    ax2.view_init(elev=ax1.elev, azim=ax1.azim)

    plt.suptitle('3D Benchmark with Smooth Interpolated Surfaces',
                 fontsize=15, fontweight='bold', y=0.98)
    plt.tight_layout()
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"Saved interpolated surface plot to {save_path}")
    plt.close()

def create_combined_surface(df, save_path='3d_benchmark_combined_surface.png'):
    """
    하나의 그래프에 두 표면을 반투명하게 겹쳐서 표시
    """
    fig = plt.figure(figsize=(16, 12))
    ax = fig.add_subplot(111, projection='3d')

    x = df['ByteOp_Count'].values
    y = df['Input_Range'].values
    z_solq = df['SolQDebug_Latency_s'].values
    z_remix = df['Remix_PureDebug_s'].values

    # 그리드 생성
    xi = np.linspace(x.min(), x.max(), 40)
    yi = np.linspace(y.min(), y.max(), 15)
    xi, yi = np.meshgrid(xi, yi)

    # 보간
    zi_solq = griddata((x, y), z_solq, (xi, yi), method='cubic', fill_value=0)
    zi_remix = griddata((x, y), z_remix, (xi, yi), method='cubic', fill_value=0)

    # SolQDebug 표면 (파란색, 반투명)
    surf1 = ax.plot_surface(xi, yi, zi_solq, cmap='Blues', alpha=0.5,
                            edgecolor='none', antialiased=True, zorder=1)

    # Remix 표면 (오렌지색, 반투명)
    surf2 = ax.plot_surface(xi, yi, zi_remix, cmap='Oranges', alpha=0.5,
                            edgecolor='none', antialiased=True, zorder=2)

    # 원본 데이터 포인트
    ax.scatter(x, y, z_solq, c='#1f77b4', marker='o', s=40, alpha=0.9,
              edgecolors='black', linewidth=0.5, zorder=10, label='SolQDebug')
    ax.scatter(x, y, z_remix, c='#ff7f0e', marker='^', s=40, alpha=0.9,
              edgecolors='black', linewidth=0.5, zorder=10, label='Remix Pure Debug')

    # Labels
    ax.set_xlabel('ByteOp Count', fontsize=12, fontweight='bold')
    ax.set_ylabel('Input Range', fontsize=12, fontweight='bold')
    ax.set_zlabel('Latency (seconds)', fontsize=12, fontweight='bold')
    ax.set_title('3D Benchmark Comparison with Overlapping Surfaces\n(SolQDebug vs Remix)',
                 fontsize=14, fontweight='bold', pad=20)

    # Legend
    ax.legend(loc='upper left', fontsize=11)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"Saved combined surface plot to {save_path}")
    plt.close()

def create_wireframe_surface(df, save_path='3d_benchmark_wireframe.png'):
    """
    Wireframe (철망) 형태의 표면
    """
    fig = plt.figure(figsize=(18, 8))

    x = df['ByteOp_Count'].values
    y = df['Input_Range'].values
    z_solq = df['SolQDebug_Latency_s'].values
    z_remix = df['Remix_PureDebug_s'].values

    # 그리드 생성
    xi = np.linspace(x.min(), x.max(), 30)
    yi = np.linspace(y.min(), y.max(), 15)
    xi, yi = np.meshgrid(xi, yi)

    # 보간
    zi_solq = griddata((x, y), z_solq, (xi, yi), method='cubic', fill_value=0)
    zi_remix = griddata((x, y), z_remix, (xi, yi), method='cubic', fill_value=0)

    # Subplot 1: SolQDebug
    ax1 = fig.add_subplot(121, projection='3d')
    ax1.plot_wireframe(xi, yi, zi_solq, color='#1f77b4', alpha=0.6, linewidth=1)
    ax1.scatter(x, y, z_solq, c='darkblue', marker='o', s=30, alpha=0.9,
               edgecolors='black', linewidth=0.5)
    ax1.set_xlabel('ByteOp Count', fontsize=11, fontweight='bold')
    ax1.set_ylabel('Input Range', fontsize=11, fontweight='bold')
    ax1.set_zlabel('Latency (s)', fontsize=11, fontweight='bold')
    ax1.set_title('SolQDebug - Wireframe', fontsize=13, fontweight='bold', pad=15)
    ax1.grid(True, alpha=0.3)

    # Subplot 2: Remix
    ax2 = fig.add_subplot(122, projection='3d')
    ax2.plot_wireframe(xi, yi, zi_remix, color='#ff7f0e', alpha=0.6, linewidth=1)
    ax2.scatter(x, y, z_remix, c='darkorange', marker='^', s=30, alpha=0.9,
               edgecolors='black', linewidth=0.5)
    ax2.set_xlabel('ByteOp Count', fontsize=11, fontweight='bold')
    ax2.set_ylabel('Input Range', fontsize=11, fontweight='bold')
    ax2.set_zlabel('Latency (s)', fontsize=11, fontweight='bold')
    ax2.set_title('Remix Pure Debug - Wireframe', fontsize=13, fontweight='bold', pad=15)
    ax2.grid(True, alpha=0.3)

    # 동일한 viewing angle
    ax2.view_init(elev=ax1.elev, azim=ax1.azim)

    plt.suptitle('3D Benchmark with Wireframe Surfaces',
                 fontsize=15, fontweight='bold', y=0.98)
    plt.tight_layout()
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"Saved wireframe plot to {save_path}")
    plt.close()

def main():
    """Generate all surface visualizations"""
    print("Loading data...")
    df = load_data()

    print("\nGenerating surface visualizations...")
    print("This may take a minute...\n")

    # Option 1: Ribbon surfaces (각 컨트랙트를 띠 모양으로 연결)
    create_contract_ribbons(df, 'Evaluation/3d_benchmark_ribbons.png')

    # Option 2: Smooth interpolated surfaces (부드러운 곡면)
    create_interpolated_surface(df, 'Evaluation/3d_benchmark_surface.png')

    # Option 3: Combined overlapping surface (하나의 그래프에 겹쳐서)
    create_combined_surface(df, 'Evaluation/3d_benchmark_combined_surface.png')

    # Option 4: Wireframe (철망 형태)
    create_wireframe_surface(df, 'Evaluation/3d_benchmark_wireframe.png')

    print("\n" + "="*70)
    print("All surface visualizations generated successfully!")
    print("="*70)
    print("\nFiles created:")
    print("  1. Evaluation/3d_benchmark_ribbons.png          - Ribbon bands per contract")
    print("  2. Evaluation/3d_benchmark_surface.png          - Smooth interpolated surfaces")
    print("  3. Evaluation/3d_benchmark_combined_surface.png - Overlapping surfaces in one plot")
    print("  4. Evaluation/3d_benchmark_wireframe.png        - Wireframe mesh")
    print("\nRecommendation:")
    print("  - For clarity: #2 (interpolated surface)")
    print("  - For comparison: #3 (combined surface)")
    print("  - For detail: #1 (ribbons)")
    print("  - For structure: #4 (wireframe)")

if __name__ == "__main__":
    main()
