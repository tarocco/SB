def walk_transforms(transform):
    yield transform
    for t in transform.children:
        yield from walk_transforms(t)
