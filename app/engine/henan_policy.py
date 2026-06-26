"""河南志愿推政策守卫（design §1 范围：仅支持河南）。"""


def assert_henan_only(province: str) -> None:
    """断言生源地为河南，否则报错。河南志愿推当前仅服务河南考生。"""
    if province != "河南":
        raise ValueError("河南志愿推仅支持河南考生")
