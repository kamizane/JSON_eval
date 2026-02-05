#import utils

##model_output = utils.load_file('ground_truth.json')

import math
import csv
import json
from jsonschema import validate
from typing import Tuple, List, Dict, Any


def jsonl_to_single_column_csv(txt_path, csv_path):
    with open(txt_path, 'r', encoding='UTF-8') as txt_file, \
         open(csv_path, 'w', newline='', encoding='UTF-8') as csv_file:

        writer = csv.writer(csv_file)
        writer.writerow(["Values"])  # cabeçalho

        for line in txt_file:
            line = line.strip()
            if not line:
                continue
            writer.writerow([line])

def compare_values(answer, model_output):
    # base case
    if isinstance(answer, (str, bool, int, float)):
            return 1 if answer == model_output else 0

    # list case
    elif isinstance(answer, list):
        # if list is empty, return 1 when model output is also empty
        if not answer:
            return 1 if (isinstance(model_output, list) and not model_output) else 0

        # if list of dict, compare index by index
        if all(isinstance(item, dict) for item in answer):
            if not isinstance(model_output, list) or not all(isinstance(item, dict) for item in model_output):
                return 0
            
            score = 0
            min_len = min(len(answer), len(model_output))
            max_len = max(len(answer), len(model_output)) ## as it is hard for list of dict to calculate union, use max length to substitute

            for i in range(min_len):
                score += compare_values(answer[i], model_output[i])

            return score / max_len if (max_len > 0) else 1
        
        # if list of base data types, compute Jaccard similarity
        else:
            if not isinstance(model_output, list):
                return 0
            
            answer_set = set(answer)
            model_output_set = set(model_output)

            common_elements = answer_set & model_output_set
            all_elements = answer_set | model_output_set

            return len(common_elements) / len(all_elements) if all_elements else 1

    # dict case   
    elif isinstance(answer, dict):
        if not isinstance(model_output, dict):
            return 0
        
        answer_keys = set(answer.keys())
        if not answer_keys: # empty dict
                return 1 if not model_output else 0
        
        all_keys = answer_keys.union(set(model_output.keys()))

        score = 0
        for key in answer_keys:
            if key in model_output:
                # compare the value in common keys recursively
                score += compare_values(answer[key], model_output[key])

        return score / len(all_keys) if all_keys else 1
    
    # other data types 
    else:
        return 0

def json_evaluation_new(model_output: str, answer: str, schema: dict):
    # try:
    #     raw_json_answer = model_output.split("```json")[-1].split("```")[0]
    # except:
    #     return 0, 0, 0, "No markdown style JSON Pattern found"
    
    try:
        model_output_json = json.loads(model_output)
    except:
        return 0, 0, 0, "Not a invalid JSON"
    
    answer_json = json.loads(answer)
    try:
        validate(instance=model_output_json, schema=schema)
    except:
        return 0, 0, 0, "JSON output doesn't match the schema"
    
    format_score = 1
    print(model_output)
    print(answer_json)
    if model_output_json == answer_json:
        strict_score = 1
    else:
        strict_score = 0

    similarity_score = compare_values(answer_json, model_output_json)

    return format_score, similarity_score, strict_score, "Give score in 3 criteria"

def compare_csv_files(file1_path: str, file2_path: str, schema: dict, 
                      model_output_col: str = 'model_output',
                      answer_col: str = 'answer',
                      output_file: str = 'comparison_results.csv') -> List[Dict[str, Any]]:
    """
    Compara dois arquivos CSV linha por linha usando a função json_evaluation_new.
    
    Args:
        file1_path: Caminho para o primeiro arquivo CSV
        file2_path: Caminho para o segundo arquivo CSV
        schema: Schema JSON para validação
        model_output_col: Nome da coluna com a saída do modelo
        answer_col: Nome da coluna com a resposta esperada
        output_file: Nome do arquivo de saída com os resultados
    
    Returns:
        Lista de dicionários com os resultados da comparação
    """
    results = []
    
    # Lê os dois arquivos CSV
    with open(file1_path, 'r', encoding='utf-8') as f1, \
         open(file2_path, 'r', encoding='utf-8') as f2:
        
        reader1 = csv.DictReader(f1)
        reader2 = csv.DictReader(f2)
        
        # Converte para listas para poder iterar juntos
        rows1 = list(reader1)
        rows2 = list(reader2)
        
        # Verifica se os arquivos têm o mesmo número de linhas
        min_rows = min(len(rows1), len(rows2))
        if len(rows1) != len(rows2):
            print(f"Atenção: Os arquivos têm números diferentes de linhas ({len(rows1)} vs {len(rows2)})")
            print(f"Comparando apenas as primeiras {min_rows} linhas")
        
        # Compara linha por linha
        for i in range(min_rows):
            row1 = rows1[i]
            row2 = rows2[i]
            
            # Extrai os valores necessários
            model_output = row1.get(model_output_col, '')
            answer = row2.get(answer_col, '')
            print(model_output == answer)
            # Realiza a avaliação
            format_score, similarity_score, strict_score, message = json_evaluation_new(
                model_output, answer, schema
            )
            
            # Armazena o resultado
            result = {
                'linha': i + 1,
                'format_score': math.trunc(format_score * 10**4) / 10**4,
                'similarity_score': math.trunc(similarity_score * 10**4) / 10**4,
                'strict_score': math.trunc(strict_score * 10**4) / 10**4,
                'message': message,
                'model_output': model_output[:100] + '...' if len(model_output) > 100 else model_output,
                'answer': answer[:100] + '...' if len(answer) > 100 else answer
            }
            results.append(result)
            
            # Imprime o progresso
            if (i + 1) % 10 == 0:
                print(f"Processadas {i + 1} linhas...")
    
    #Salva os resultados em um arquivo CSV
    if results:
        with open(output_file, 'w', encoding='utf-8', newline='') as f:
            fieldnames = ['linha', 'format_score', 'similarity_score', 'strict_score', 
                         'message', 'model_output', 'answer']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)
        
        print(f"\nResultados salvos em: {output_file}")
    
    #Calcula e imprime estatísticas
    print_statistics(results)
    
    return results


def print_statistics(results: List[Dict[str, Any]]):
    """Imprime estatísticas dos resultados da comparação."""
    if not results:
        print("Nenhum resultado para exibir")
        return
    
    total = len(results)
    avg_format = sum(r['format_score'] for r in results) / total
    avg_similarity = sum(r['similarity_score'] for r in results) / total
    avg_strict = sum(r['strict_score'] for r in results) / total
    
    print("\n" + "="*50)
    print("ESTATÍSTICAS DA COMPARAÇÃO")
    print("="*50)
    print(f"Total de linhas comparadas: {total}")
    print(f"Format Score médio: {avg_format:.4f}")
    print(f"Similarity Score médio: {avg_similarity:.4f}")
    print(f"Strict Score médio: {avg_strict:.4f}")
    print(f"Correspondências exatas: {sum(r['strict_score'] for r in results)} ({avg_strict*100:.2f}%)")
    print("="*50)


if __name__ == "__main__":
    #Define o schema JSON de exemplo
    schema_exemplo = {
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["basemats", "dopants", "dopants2basemats"],
  "properties": {
    "basemats": {
      "type": "object",
      "additionalProperties": {
        "type": "string"
      }
    },
    "dopants": {
      "type": "object",
      "additionalProperties": {
        "type": "string"
      }
    },
    "dopants2basemats": {
      "type": "object",
      "additionalProperties": {
        "type": "array",
        "items": {
          "type": "string"
        }
      }
    }
  },
  "additionalProperties": False
}


# schema_exemplo = {
#     "type": "object",
#     "properties": {
#         "basemats": {
#             "type": "object",
#             "additionalProperties": {
#                 "type": "string"
#             }
#         },
#         "dopants": {
#             "type": "object",
#             "additionalProperties": {
#                 "type": "string"
#             }
#         },
#         "dopants2basemats": {
#             "type": "object",
#             "additionalProperties": {
#                 "type": "array",
#                 "items": {
#                     "type": "string"
#                 }
#             }
#         }
#     },
#     "required": ["basemats", "dopants", "dopants2basemats"],
#     "additionalProperties": False
# }

    
    
    jsonl_to_single_column_csv(
    "testeGT.txt",
    "testeGT.csv"
    )
    jsonl_to_single_column_csv(
    "testeGT.txt",
    "testeP.csv"
    )

    #Caminhos dos arquivos
    ground_truth = "testeGT.csv"
    output = "testeP.csv"

    #Executa a comparação
    resultados = compare_csv_files(
        file1_path=ground_truth,
        file2_path=output,
        schema=schema_exemplo,
        model_output_col='Values',  # Altere para o nome da sua coluna
        answer_col='Values',               # Altere para o nome da sua coluna
        output_file='resultados_comparacao.csv'
    )