import re

with open('raspi_main/static/script.js', 'r', encoding='utf-8') as f:
    content = f.read()

content = re.sub(r'const btnSelectTarget\s*=\s*document\.getElementById\([\'"]btn-select-target[\'"]\);\n', '', content)
content = re.sub(r'const btnAddLearning\s*=\s*document\.getElementById\([\'"]btn-add-learning[\'"]\);\n', '', content)
content = re.sub(r'const targetTypeModal\s*=\s*document\.getElementById\([\'"]target-type-modal[\'"]\);\n', '', content)
content = re.sub(r'const moreLearnModal\s*=\s*document\.getElementById\([\'"]more-learn-modal[\'"]\);\n', '', content)
content = re.sub(r'const learnOverlay\s*=\s*document\.getElementById\([\'"]learn-overlay[\'"]\);\n', '', content)
content = re.sub(r'const targetPreviewRow\s*=\s*document\.getElementById\([\'"]target-preview-row[\'"]\);\n', '', content)

content = re.sub(r'if \(\s*btnSelectTarget\s*\)\s*\{.*?\n\}\n', '', content, flags=re.DOTALL)
content = re.sub(r'if \(\s*btnAddLearning\s*\)\s*\{.*?\n\}\n', '', content, flags=re.DOTALL)
content = re.sub(r'if \(\s*btnClearTarget\s*\)\s*\{.*?\n\}\n', '', content, flags=re.DOTALL)

with open('raspi_main/static/script.js', 'w', encoding='utf-8') as f:
    f.write(content)
print('Cleaned UI references')
