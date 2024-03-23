from transformers import AutoTokenizer
from config import MODEL_NAME, GPT_URL
import requests
import logging

logging.basicConfig(filename='log.txt', level=logging.DEBUG,
                    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", filemode="w")
 
def count_tokens(text):
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    return len(tokenizer.encode(text))

def ask_gpt(task, system_content, answer=''):
    assistant_content = 'Решим задачу по шагам: ' + answer
    response = requests.post(
        GPT_URL,
        headers = {'Content-Type': 'application/json'},
        json = {
            "messages": [
                {"role": "user", "content": task},
                {"role": "system", "content": system_content},
                {"role": "assistant", "content": assistant_content}
            ],
            "temperature": 1,
            "max_tokens": 512,
        }
    )
    if response.status_code == 200:
        result = response.json()['choices'][0]['message']['content']
        logging.debug(f'Действие: {task}, Результат: {result}')
        return result
    else:
        logging.info(f'Действие: {task}, Результат: {response.json()}')
        return 'Error'
