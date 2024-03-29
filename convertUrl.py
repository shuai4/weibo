
ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"


def base62_encode(num, alphabet=ALPHABET):
    """Encode a number in Base X

    `num`: The number to encode
    `alphabet`: The alphabet to use for encoding
    """
    if (num == 0):
        return alphabet[0]
    arr = []
    base = len(alphabet)
    while num:
        rem = num % base
        num = num // base
        arr.append(alphabet[rem])
    arr.reverse()
    return ''.join(arr)


def base62_decode(string, alphabet=ALPHABET):
    """Decode a Base X encoded string into the number

    Arguments:
    - `string`: The encoded string
    - `alphabet`: The alphabet to use for encoding
    """
    base = len(alphabet)
    strlen = len(string)
    num = 0

    idx = 0
    for char in string:
        power = (strlen - (idx + 1))
        num += alphabet.index(char) * (base ** power)
        idx += 1
    return num


def gid_to_mid(url):
    '''
    >>> gid_to_mid('z0JH2lOMb')
    3501756485200075L
    >>> gid_to_mid('z0Ijpwgk7')
    3501703397689247L
    >>> gid_to_mid('z0IgABdSn')
    3501701648871479L
    >>> gid_to_mid('z08AUBmUe')
    3500330408906190L
    >>> gid_to_mid('z06qL6b28')
    3500247231472384L
    >>> gid_to_mid('yCtxn8IXR')
    3491700092079471L
    >>> gid_to_mid('yAt1n2xRa')
    3486913690606804L
    '''
    url = str(url)[::-1]
    size = len(url) / 4 if len(url) % 4 == 0 else int(len(url) / 4) + 1
    result = []
    for i in range(size):
        s = url[i * 4: (i + 1) * 4][::-1]
        s = str(base62_decode(str(s)))
        s_len = len(s)
        if i < size - 1 and s_len < 7:
            s = (7 - s_len) * '0' + s
        result.append(s)
    result.reverse()
    return int(''.join(result))


def mid_to_gid(midint):
    '''
    >>> mid_to_gid(3501756485200075)
    'z0JH2lOMb'
    >>> mid_to_gid(3501703397689247)
    'z0Ijpwgk7'
    >>> mid_to_gid(3501701648871479)
    'z0IgABdSn'
    >>> mid_to_gid(3500330408906190)
    'z08AUBmUe'
    >>> mid_to_gid(3500247231472384)
    'z06qL6b28'
    >>> mid_to_gid(3491700092079471)
    'yCtxn8IXR'
    >>> mid_to_gid(3486913690606804)
    'yAt1n2xRa'
    '''
    midint = str(midint)[::-1]
    size = len(midint) / \
        7 if len(midint) % 7 == 0 else int(len(midint) / 7) + 1
    result = []
    for i in range(size):
        s = midint[i * 7: (i + 1) * 7][::-1]
        s = base62_encode(int(s))
        s_len = len(s)
        if i < size - 1 and len(s) < 4:
            s = '0' * (4 - s_len) + s
        result.append(s)
    result.reverse()
    return ''.join(result)


def gen_pcurl(uid, mid):
    gid = mid_to_gid(mid)
    blog_url = 'https://weibo.com/{uid}/{gid}'.format(uid=uid, gid=gid)
    print(blog_url)
    return blog_url
