from flask import request


def paginate(query):
    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("pageSize", 20, type=int)

    pagination = query.paginate(page=page, per_page=page_size)

    return {
        "items": pagination.items,
        "total": pagination.total,
        "page": page,
        "pages": pagination.pages,
    }
