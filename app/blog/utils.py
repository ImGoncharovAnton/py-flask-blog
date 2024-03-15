from math import ceil

# Translate table
translit_table = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e', 'ж': 'zh', 'з': 'z',
    'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r',
    'с': 's', 'т': 't', 'у': 'u', 'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
    'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya'
}


def transliterate(text):
    return ''.join(translit_table.get(char, char) for char in text.lower())


def slugify(title):
    transliterated_title = transliterate(title)
    return transliterated_title.lower().replace(' ', '-')


def pagination(count, page, per_page=2):
    page_no = ceil(count / per_page)
    offset = (page - 1) * per_page
    next_page = page + 1
    prev_page = page - 1
    return {
        'per_page': per_page,
        'offset': offset,
        'pages': list(range(1, page_no + 1)),
        'page': page,
        'page_no': page_no,
        'next_page': next_page,
        'prev_page': prev_page
    }
