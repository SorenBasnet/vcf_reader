import csv
import math
import json
from pathlib import Path

def parse_gwas_tsv(gwas_file: str, max_points: int = 10000):
    """Parses GWAS TSV and extracts chromosome, position, and -log10(p-value)."""
    chroms, positions, neg_log_p, variant_ids = [], [], [], []
    
    with open(gwas_file, "r") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for i, row in enumerate(reader):
            if i >= max_points:
                break
            try:
                p_val = float(row["P"])
                if p_val <= 0:
                    continue
                
                # Calculate -log10(p)
                log_p = -math.log10(p_val)
                
                chroms.append(str(row["CHROM"]))
                positions.append(int(row["POS"]))
                neg_log_p.append(round(log_p, 3))
                variant_ids.append(row["ID"])
            except (KeyError, ValueError):
                continue
                
    return {
        "chrom": chroms,
        "pos": positions,
        "log_p": neg_log_p,
        "ids": variant_ids
    }

def generate_web_report(repo_dir: str, gwas_file: str) -> Path:
    report_path = Path(repo_dir) / "index.html"
    plot_data = parse_gwas_tsv(gwas_file)
    
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Cintern Genomic Repository</title>
    <script src="https://cdn.plot.ly/plotly-2.26.0.min.js"></script>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 0; background-color: #0d1117; color: #c9d1d9; }}
        .header {{ background-color: #161b22; border-bottom: 1px solid #30363d; padding: 16px 32px; display: flex; justify-content: space-between; align-items: center; }}
        .container {{ padding: 32px; max-width: 1300px; margin: 0 auto; }}
        .card {{ background: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 24px; margin-top: 16px; }}
        .tag {{ background: #238636; color: #fff; padding: 4px 10px; border-radius: 12px; font-size: 12px; font-weight: bold; }}
    </style>
</head>
<body>
    <div class="header">
        <h2>cintern / <span id="repo-title">gwas_results_repo</span></h2>
        <span class="tag">Published</span>
    </div>
    <div class="container">
        <div class="card">
            <h3>Interactive Manhattan Plot</h3>
            <p>Genome-wide association study findings (-log10 p-values across genomic coordinates).</p>
            <div id="manhattan-plot" style="height: 500px;"></div>
        </div>
    </div>

    <script>
        const plotData = {json.dumps(plot_data)};
        
        const trace = {{
            x: plotData.pos,
            y: plotData.log_p,
            text: plotData.ids,
            mode: 'markers',
            type: 'scattergl',
            marker: {{
                size: 6,
                color: plotData.log_p,
                colorscale: 'Viridis',
                showscale: true
            }}
        }};

        const layout = {{
            paper_bgcolor: '#161b22',
            plot_bgcolor: '#161b22',
            font: {{ color: '#c9d1d9' }},
            xaxis: {{ title: 'Genomic Position', gridcolor: '#21262d' }},
            yaxis: {{ title: '-log10(p-value)', gridcolor: '#21262d' }},
            shapes: [{{
                type: 'line',
                x0: 0,
                x1: 1,
                xref: 'paper',
                y0: 7.3,
                y1: 7.3,
                line: {{ color: '#f85149', width: 1.5, dash: 'dash' }}
            }}]
        }};

        Plotly.newPlot('manhattan-plot', [trace], layout);
    </script>
</body>
</html>
"""
    with open(report_path, "w") as f:
        f.write(html_content)
    
    return report_path
