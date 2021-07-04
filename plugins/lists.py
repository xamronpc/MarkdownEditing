import re

from .view import MdeTextCommand


class MdeUnIndentListItemCommand(MdeTextCommand):
    """
    This is an interanal text command class shared by `(un)indent_list_item` commands.

    It is responsible to read settings and cycle through all selections to replace text.
    """

    def run(self, edit):
        queue = []

        view = self.view
        settings = view.settings()
        bullets = settings.get("mde.list_indent_bullets", ["*", "-", "+"])
        if settings.get("mde.list_indent_auto_switch_bullet", True):
            new_bullets = bullets
        else:
            new_bullets = None

        if settings.get("translate_tabs_to_spaces"):
            tab_str = " " * settings.get("tab_size", 4)
        else:
            tab_str = "\t"

        pattern = re.compile(
            r"^(?:[\s>]*>\s)?(\s*)(?:([%s])\s)?" % "".join(re.escape(bullet) for bullet in bullets)
        )

        for sel in view.sel():
            for region in view.split_by_newlines(view.line(sel)):
                match = re.search(pattern, view.substr(region))
                if not match:
                    continue

                indent, bullet = match.groups()
                text = self.compute_replacement(indent, tab_str, bullet, new_bullets)
                if text is None:
                    continue

                # setup region to replace based on pattern match
                region.b = region.a + max(match.end(1), match.end(2))
                region.a += match.start(1)

                queue.append([region, text])

        for r, text in reversed(queue):
            view.replace(edit, r, text)


class MdeIndentListItemCommand(MdeUnIndentListItemCommand):
    """
    The `mde_indent_list_item` command indents unordered list items.

    It indents lists within blockquotes.
    It changes list bullet according to indentation level
    if `mde.list_indent_auto_switch_bullet` is set `true`.
    """

    def compute_replacement(self, indent, tab_str, bullet, bullets):
        text = indent + tab_str
        if bullet:
            if bullets:
                text += bullets[(bullets.index(bullet) + 1) % len(bullets)]
            else:
                text += bullet
        return text


class MdeUnindentListItemCommand(MdeUnIndentListItemCommand):
    """
    The `mde_unindent_list_item` command unindents unordered list items.

    It unindents lists within blockquotes.
    It changes list bullet according to indentation level.
    if `mde.list_indent_auto_switch_bullet` is set `true`.
    """

    def compute_replacement(self, indent, tab_str, bullet, bullets):
        if not indent:
            return None

        text = indent.replace(tab_str, "", 1)
        if bullet:
            if bullets:
                text += bullets[(bullets.index(bullet) - 1) % len(bullets)]
            else:
                text += bullet
        return text


class MdeSwitchListBulletTypeCommand(MdeTextCommand):
    """
    The `mde_switch_list_bullet_type` command converts selected list items to ordered and unordered.

    Each selected item is evaluated separately.
    """

    def run(self, edit):
        align_text = self.view.settings().get("mde.list_align_text", True)
        auto_increment = self.view.settings().get("mde.auto_increment_ordered_list_number", True)
        bullets = self.view.settings().get("mde.list_indent_bullets", ["*", "-", "+"])
        pattern = re.compile(
            r"^\s*(?:>\s*)*(?:([%s])|([0-9]+\.))(\s+)"
            % "".join(re.escape(bullet) for bullet in bullets)
        )

        for sel in self.view.sel():
            idx = 1
            for region in self.view.split_by_newlines(self.view.line(sel)):
                text = self.view.substr(region)
                match = pattern.search(text)
                if not match:
                    continue

                bullet, number, space = match.groups()
                if bullet:
                    # Transform unordered to ordered list
                    new_text = str(idx) + "."
                    if auto_increment:
                        idx += 1

                    region.a += match.start(1)
                    region.b = region.a + min(len(new_text), max(1, len(space)))
                    self.view.replace(edit, region, new_text)

                elif number:
                    # Transform ordered to unordered list
                    region.a += match.start(2)
                    if align_text:
                        new_text = bullets[0] + " " * len(number)
                        region.b = region.a + len(new_text)
                    else:
                        new_text = bullets[0]
                        region.b = region.a + len(number)
                    self.view.replace(edit, region, new_text)


class MdeNumberListCommand(MdeTextCommand):
    def run(self, edit):
        view = self.view
        sel = view.sel()[0]
        text = view.substr(view.full_line(sel))
        num = re.search(r"\d", text).start()
        dot = text.find(".")
        additional_spaces = re.search(r"^\s*", text[dot + 1 :]).group()
        increment = 0
        if self.view.settings().get("mde.auto_increment_ordered_list_number", True):
            increment = 1
        if num == 0:
            view.erase(edit, sel)
            view.insert(
                edit, sel.begin(), "\n%d.%s" % (int(text[:dot]) + increment, additional_spaces)
            )
        else:
            view.erase(edit, sel)
            view.insert(
                edit,
                sel.begin(),
                "\n%s%d.%s" % (text[:num], int(text[num:dot]) + increment, additional_spaces),
            )


class MdeToggleTaskListItemCommand(MdeTextCommand):
    """
    The `mde_toggle_task_list_item` command toggles the check mark of task list items.

    It must be called in the line of the check mark.

    **Examples:**

    ```markdown
    # Orderd Task List

    1. [ ] task 1
    2. [X] task 2

    # Unorderd Task List

    * [ ] task 1
    - [X] task 2
    + [ ] task 3

    # Quoted Task List

    > * [ ] task 1
    > * [X] task 2
    ```
    """

    def run(self, edit):
        bullets = self.view.settings().get("mde.list_indent_bullets", ["*", "-", "+"])
        pattern = re.compile(
            r"^(\s*(?:>\s*)*(?:[%s]|[0-9]+\.)\s+\[)([ xX])\]\s"
            % "".join(re.escape(bullet) for bullet in bullets)
        )

        for sel in self.view.sel():
            for region in self.view.split_by_newlines(self.view.line(sel)):
                region.b = min(region.b, region.a + 50)
                match = pattern.search(self.view.substr(region))
                if not match:
                    continue

                # calculate text position of check mark
                region.a += len(match.group(1))
                region.b = region.a + 1

                mark = "X" if match.group(2) == " " else " "
                self.view.replace(edit, region, mark)