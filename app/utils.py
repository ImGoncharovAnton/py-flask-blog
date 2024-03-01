def form_errors(*args):
    errors = {}
    for field in args:
        errors[field] = None
    errors['blank'] = 'This field must not be blank'
    return errors


def validate(error_fields, *args):
    name_list = list(error_fields.keys())

    def check(tup):
        index, field = tup
        if not field:
            error_fields[name_list[index]] = error_fields['blank']
        return field

    list(map(check, enumerate(args)))
    return error_fields
