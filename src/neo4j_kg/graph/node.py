"""
node.py
===============

A short discription about this module

Detail:
    This module provides classes and methods for building ontology of KG for legal articles.
"""


from typing import List, Optional
from abc import ABC, abstractmethod
import uuid

from neo4j_client.relation import Relation
# from sample_uuid import generate_unique_id


class NodeABC(ABC):

    """Represents a base node of KG.

    Attributes:
        name (str): The node's name.
        id (str): The node's id (Optional).
        code (str): The node's code (Optional).
    """

    def __init__(self, name: str, id: str = "", code: str = ""):
        """Initialize a NodeABC instance.

        Args:
            name (str): The node's name.
            id (str): The node's id. Defaults to "".
            code (str): The node's code . Defaults to "".
        """
        self.name = name
        self.id = id
        self.code = code
    
    @abstractmethod
    def get_content(self):
        """Return compiled content of node.

        This method should be overridden by subclasses.

        Raises:
            NotImplementedError: If called on the base class.

        Returns:
            str: The content of the node that is compiled over all children of it.
        """
        raise NotImplementedError


class ArticleLog(NodeABC):

    def __init__(self, name: str, id: str = "", code: str = "",
                 content: str = "", available_time: str = "",
                 link: str = "", relation: str = "", log_name_id_map: dict = {}):
        """Initialize a ArticleLog instance.

        Args:
            name (str): The article log's name.
            id (str): The article log's id. Defaults to "".
            code (str): The article log's code . Defaults to "".
            content (str): The article log's content . Defaults to "".
        """
        super().__init__(name=name, id=id, code=code)
        self._content = content
        self.available_time = available_time
        self.link = link
        self.relation = "unknown" if relation == "Chưa biết" else relation
        self.id = id
    def get_content(self):
        """Return content of article log.

        Returns:
            str: The content of article log.
        """
        return self._content

    def insert_neo4j(self, neo4j_client):
        neo4j_client.insert_nodes_if_not_exist("ArticleLog", [{"id": self.id, "name": self.name,
                                                               "code": self.code,
                                                               "content": self.get_content(),
                                                               "available_time": self.available_time,
                                                               "link": self.link}])
        return self.id

    def get_data(self, data):
        if self.id in [a["id"] for a in data["nodes"] if a["node_type"] == "ArticleLog"]:
            return data
        data["nodes"].append({"node_type": "ArticleLog", "id": self.id, "name": self.name, "code": self.code,
                              "content": self.get_content(), "available_time": self.available_time,
                              "link": self.link})
        return data

class Document(NodeABC):

    def __init__(self, name: str, id: str = ""):
        """Initialize a Document instance.
        Args:
            name (str): The document's name.
            id (str): The document's id. Defaults to "".
        """
        super().__init__(name=name, id=id)

class Article(NodeABC):

    def __init__(self, name: str, id: str = "", code: str = "", content: str = "", relevance_articles: List = [],
                 raw_article_logs: dict = {}, log_name_id_map: dict = {}, doc_name: str = ""):
        """Initialize an Article instance.

        Args:
            name (str): The article's name.
            id (str): The article's id. Defaults to "".
            code (str): The article's code . Defaults to "".
            article_logs (list): The list of article logs describles the initialization and updates of article
        """
        super().__init__(name=name, id=id, code=code)
        self.content = content
        self.relevance_articles = relevance_articles
        self.note, self.article_logs = self.get_article_logs(raw_article_logs, log_name_id_map)
        self.doc_name = doc_name
    
    def get_article_logs(self, raw_article_logs, log_name_id_map):
        if isinstance(raw_article_logs, list):
            if len(raw_article_logs):
                print(raw_article_logs)
                assert False 
            else:
                return "", []
        note = raw_article_logs.get("Ghi chú", "")
        metadata = raw_article_logs.get("metadata", [])
        if isinstance(metadata, list):
            article_logs = [ArticleLog(
                id=log_name_id_map[a["Tên điều"]],
                name=a["Tên điều"],
                available_time=a["Hiệu lực"],
                link=a.get("Link", ""),
                relation=a["Thi hành"],
                log_name_id_map= log_name_id_map
                ) for a in metadata]
        else:
            article_logs = []
        return note, article_logs
    
    def get_content(self):
        """Return the latest content of article.

        Raises:
            NotImplementedError: If called on the base class.

        Returns:
            str: The latest content of the article based on latest article log.
        """
        pass

    def structure_represent(self, tab_index):
        tab = "\t"*tab_index
        represent = f"\n{tab}name: {self.name} --- id: {self.id} --- code: {self.code}\n"
        return represent
    
    def insert_neo4j(self, neo4j_client):
        neo4j_client.insert_nodes_if_not_exist("Article", [{"id": self.id, "name": self.name, "code": self.code, "content": self.content}])
        for article_log in self.article_logs:
            article_log_id = article_log.insert_neo4j(neo4j_client)
            relation = article_log.relation
            neo4j_client.insert_include_batch("Article", "ArticleLog", relation, [{"from_id": self.id, "to_id": article_log_id}])
        return self.id
    
    def get_data(self, data):
        data["nodes"].append({"node_type": "Article", "id": self.id, "name": self.name, "code": self.code, "content": self.content})

        for article_log in self.article_logs:
            data = article_log.get_data(data)
            if data["relations"].get("Article_ArticleLog", None) is None:
                data["relations"]["Article_ArticleLog"] = {}
            if data["relations"]["Article_ArticleLog"].get(article_log.relation, None):
                data["relations"]["Article_ArticleLog"][article_log.relation].append({"from_id": self.id, "to_id": article_log.id})
            else:
                data["relations"]["Article_ArticleLog"][article_log.relation] = [{"from_id": self.id, "to_id": article_log.id}]
        return data

    def append_article_logs(self, list_article_logs: Optional[List[ArticleLog]] = []):
        """Update article_logs attribute.

        Returns:
            void: Append new update article_logs and article's content.
        """
        self.article_logs.extend(list_article_logs)


class SubSection(NodeABC):

    def __init__(self, name: str, id: str = "", code: str = ""):
        """Initialize a SubSection instance.

        Args:
            name (str): The subsection's name.
            id (str): The subsection's id. Defaults to "".
            code (str): The subsection's code . Defaults to "".
            articles (list): The list of articles of this subsection.
        """
        super().__init__(name=name, id=id, code=code)
        self.articles = []
    
    def structure_represent(self, tab_index):
        tab = "\t"*tab_index
        represent = f"{tab}SUBSECTION\n{tab}name: {self.name} --- id: {self.id} --- code: {self.code}\n"
        if len(self.articles):
            represent += f"{tab}\tARTICLE\n"
        for article in self.articles:
            represent += article.structure_represent(tab_index+1)
        return represent
    
    def insert_neo4j(self, neo4j_client):
        neo4j_client.insert_nodes_if_not_exist("Subsection", [{"id": self.id, "name": self.name, "code": self.code}])

        article_ids = []
        for article in self.articles:
            article_id = article.insert_neo4j(neo4j_client)
            article_ids.append(article_id)
        neo4j_client.insert_include_batch("Subsection", "Article", Relation.INCLUDE, [{"from_id": self.id, "to_id": t_id} for t_id in article_ids])
        
        return self.id
    
    def get_data(self, data):
        data["nodes"].append({"node_type": "SubSection", "id": self.id, "name": self.name, "code": self.code})

        for article in self.articles:
            data = article.get_data(data)
            if data["relations"].get("SubSection_Article", None):
                data["relations"]["SubSection_Article"][Relation.INCLUDE].append({"from_id": self.id, "to_id": article.id})
            else:
                data["relations"]["SubSection_Article"] = {}
                data["relations"]["SubSection_Article"][Relation.INCLUDE] = [{"from_id": self.id, "to_id": article.id}]
        return data

    def get_content(self):
        """Return compiled content of subsection over all it's articles.

        Raises:
            NotImplementedError: If called on the base class.

        Returns:
            str: The compiled content of the subsection based on all article's content.
        """
        pass

    def append_articles(self, list_articles: Optional[List[Article]] = []):
        """Update articles attribute.

        Returns:
            void: Append new update articles and subsection's content.
        """
        self.articles.extend(list_articles)


class Section(NodeABC):

    def __init__(self, name: str, id: str = "", code: str = ""):
        """Initialize a Section instance.

        Args:
            name (str): The section's name.
            id (str): The section's id. Defaults to "".
            code (str): The section's code . Defaults to "".
            subsections (list): The list of subsections of this section.
            articles (list): The list of articles of this section.
        """
        super().__init__(name=name, id=id, code=code)
        self.subsections = []
        self.articles = []
    
    def structure_represent(self, tab_index):
        tab = "\t"*tab_index
        represent = f"{tab}SECTION\n{tab}name: {self.name} --- id: {self.id} --- code: {self.code}\n"
        for subsection in self.subsections:
            represent += subsection.structure_represent(tab_index+1)
        if len(self.articles):
            represent += f"{tab}\tARTICLE\n"
        for article in self.articles:
            represent += article.structure_represent(tab_index+1)
        return represent
    
    def insert_neo4j(self, neo4j_client):
        neo4j_client.insert_nodes_if_not_exist("Section", [{"id": self.id, "name": self.name, "code": self.code}])

        subsection_ids = []
        for subsection in self.subsections:
            subsection_id = subsection.insert_neo4j(neo4j_client)
            subsection_ids.append(subsection_id)
        neo4j_client.insert_include_batch("Section", "Subsection", Relation.INCLUDE, [{"from_id": self.id, "to_id": t_id} for t_id in subsection_ids])
        
        article_ids = []
        for article in self.articles:
            article_id = article.insert_neo4j(neo4j_client)
            article_ids.append(article_id)
        neo4j_client.insert_include_batch("Section", "Article", Relation.INCLUDE, [{"from_id": self.id, "to_id": t_id} for t_id in article_ids])
        
        return self.id

    def get_data(self, data):
        data["nodes"].append({"node_type": "Section", "id": self.id, "name": self.name, "code": self.code})

        for subsection in self.subsections:
            data = subsection.get_data(data)
            if data["relations"].get("Section_SubSection", None):
                data["relations"]["Section_SubSection"][Relation.INCLUDE].append({"from_id": self.id, "to_id": subsection.id})
            else:
                data["relations"]["Section_SubSection"] = {}
                data["relations"]["Section_SubSection"][Relation.INCLUDE] = [{"from_id": self.id, "to_id": subsection.id}]

        for article in self.articles:
            data = article.get_data(data)
            if data["relations"].get("Section_Article", None):
                data["relations"]["Section_Article"][Relation.INCLUDE].append({"from_id": self.id, "to_id": article.id})
            else:
                data["relations"]["Section_Article"] = {}
                data["relations"]["Section_Article"][Relation.INCLUDE] = [{"from_id": self.id, "to_id": article.id}]
        return data

    def get_content(self):
        """Return compiled content of section over all it's subsections and articles.

        Raises:
            NotImplementedError: If called on the base class.

        Returns:
            str: The compiled content of the section based on all subsections's content and article's content.
        """
        pass

    def append_subsections(self, list_subsections: Optional[List[SubSection]] = []):
        """Update articles attribute.

        Returns:
            void: Append new update subsection and section's content.
        """
        self.subsections.extend(list_subsections)

    def append_articles(self, list_articles: Optional[List[Article]] = []):
        """Update articles attribute.

        Returns:
            void: Append new update articles and section's content.
        """
        self.articles.extend(list_articles)


class Chapter(NodeABC):

    def __init__(self, name: str, id: str = "", code: str = ""):
        """Initialize a Chapter instance.

        Args:
            name (str): The chapter's name.
            id (str): The chapter's id. Defaults to "".
            code (str): The chapter's code . Defaults to "".
            sections (list): The list of sections of this chapter.
            subsections (list): The list of subsections of this chapter.
            articles (list): The list of articles of this chapter.
        """
        super().__init__(name=name, id=id, code=code)
        self.sections = []
        self.subsections = []
        self.articles = []
    
    def structure_represent(self, tab_index):
        tab = "\t"*tab_index
        represent = f"{tab}CHAPTER\n{tab}name: {self.name} --- id: {self.id} --- code: {self.code}\n"
        for section in self.sections:
            represent += section.structure_represent(tab_index+1)
        for subsection in self.subsections:
            represent += subsection.structure_represent(tab_index+1)
        if len(self.articles):
            represent += f"{tab}\tARTICLE\n"
        for article in self.articles:
            represent += article.structure_represent(tab_index+1)
        return represent
    
    def insert_neo4j(self, neo4j_client):
        neo4j_client.insert_nodes_if_not_exist("Chapter", [{"id": self.id, "name": self.name, "code": self.code}])

        section_ids = []
        for section in self.sections:
            section_id = section.insert_neo4j(neo4j_client)
            section_ids.append(section_id)
        neo4j_client.insert_include_batch("Chapter", "Section", Relation.INCLUDE, [{"from_id": self.id, "to_id": t_id} for t_id in section_ids])

        subsection_ids = []
        for subsection in self.subsections:
            subsection_id = subsection.insert_neo4j(neo4j_client)
            subsection_ids.append(subsection_id)
        neo4j_client.insert_include_batch("Chapter", "Subsection", Relation.INCLUDE, [{"from_id": self.id, "to_id": t_id} for t_id in subsection_ids])
        
        article_ids = []
        for article in self.articles:
            article_id = article.insert_neo4j(neo4j_client)
            article_ids.append(article_id)
        neo4j_client.insert_include_batch("Chapter", "Article", Relation.INCLUDE, [{"from_id": self.id, "to_id": t_id} for t_id in article_ids])
        
        return self.id

    def get_data(self, data):
        data["nodes"].append({"node_type": "Chapter", "id": self.id, "name": self.name, "code": self.code})

        for section in self.sections:
            data = section.get_data(data)
            if data["relations"].get("Chapter_Section", None):
                data["relations"]["Chapter_Section"][Relation.INCLUDE].append({"from_id": self.id, "to_id": section.id})
            else:
                data["relations"]["Chapter_Section"] = {}
                data["relations"]["Chapter_Section"][Relation.INCLUDE] = [{"from_id": self.id, "to_id": section.id}]

        for subsection in self.subsections:
            data = subsection.get_data(data)
            if data["relations"].get("Chapter_SubSection", None):
                data["relations"]["Chapter_SubSection"][Relation.INCLUDE].append({"from_id": self.id, "to_id": subsection.id})
            else:
                data["relations"]["Chapter_SubSection"] = {}
                data["relations"]["Chapter_SubSection"][Relation.INCLUDE] = [{"from_id": self.id, "to_id": subsection.id}]

        for article in self.articles:
            data = article.get_data(data)
            if data["relations"].get("Chapter_Article", None):
                data["relations"]["Chapter_Article"][Relation.INCLUDE].append({"from_id": self.id, "to_id": article.id})
            else:
                data["relations"]["Chapter_Article"] = {}
                data["relations"]["Chapter_Article"][Relation.INCLUDE] = [{"from_id": self.id, "to_id": article.id}]
        return data

    def get_content(self):
        """Return compiled content of chapter over all it's sections,  subsections and articles.

        Raises:
            NotImplementedError: If called on the base class.

        Returns:
            str: The compiled content of the chapter based on all sections, subsections's content and article's content.
        """
        pass

    def append_sections(self, list_sections: Optional[List[Section]] = []):
        """Update sections attribute.

        Returns:
            void: Append new update sections and chapter's content.
        """
        self.sections.extend(list_sections)

    def append_subsections(self, list_subsections: Optional[List[SubSection]] = []):
        """Update subsections attribute.

        Returns:
            void: Append new update subsections and chapter's content.
        """
        self.subsections.extend(list_subsections)
    
    def append_articles(self, list_articles: Optional[List[Article]] = []):
        """Update articles attribute.

        Returns:
            void: Append new update articles and chapter's content.
        """
        self.articles.extend(list_articles)


class Part(NodeABC):

    def __init__(self, name: str, id: str = "", code: str = ""):
        """Initialize a Part instance.

        Args:
            name (str): The part's name.
            id (str): The part's id. Defaults to "".
            code (str): The part's code . Defaults to "".
            chapters (list): The list of chapters of this part.
            sections (list): The list of sections of this part.
            subsections (list): The list of subsections of this part.
            articles (list): The list of articles of this part.
        """
        super().__init__(name=name, id=id, code=code)
        self.chapters = []
        self.sections = []
        self.subsections = []
        self.articles = []
    
    def structure_represent(self, tab_index):
        tab = "\t" * tab_index 
        represent = f"{tab}PART\n{tab}name: {self.name} --- id: {self.id} --- code: {self.code}\n"
        for chapter in self.chapters:
            represent += chapter.structure_represent(tab_index+1)
        for section in self.sections:
            represent += section.structure_represent(tab_index+1)
        for subsection in self.subsections:
            represent += subsection.structure_represent(tab_index+1)
        if len(self.articles):
            represent += f"{tab}\tARTICLE\n"
        for article in self.articles:
            represent += article.structure_represent(tab_index+1)
        return represent

    def insert_neo4j(self, neo4j_client):
        neo4j_client.insert_nodes_if_not_exist("Part", [{"id": self.id, "name": self.name, "code": self.code}])
        chapter_ids = []
        for chapter in self.chapters:
            chapter_id = chapter.insert_neo4j(neo4j_client)
            chapter_ids.append(chapter_id)
        neo4j_client.insert_include_batch("Part", "Chapter", Relation.INCLUDE, [{"from_id": self.id, "to_id": t_id} for t_id in chapter_ids])

        section_ids = []
        for section in self.sections:
            section_id = section.insert_neo4j(neo4j_client)
            section_ids.append(section_id)
        neo4j_client.insert_include_batch("Part", "Section", Relation.INCLUDE, [{"from_id": self.id, "to_id": t_id} for t_id in section_ids])

        subsection_ids = []
        for subsection in self.subsections:
            subsection_id = subsection.insert_neo4j(neo4j_client)
            subsection_ids.append(subsection_id)
        neo4j_client.insert_include_batch("Part", "Subsection", Relation.INCLUDE, [{"from_id": self.id, "to_id": t_id} for t_id in subsection_ids])
        
        article_ids = []
        for article in self.articles:
            article_id = article.insert_neo4j(neo4j_client)
            article_ids.append(article_id)
        neo4j_client.insert_include_batch("Part", "Article", Relation.INCLUDE, [{"from_id": self.id, "to_id": t_id} for t_id in article_ids])
        
        return self.id

    def get_data(self, data):

        data["nodes"].append({"node_type": "Part", "id": self.id, "name": self.name, "code": self.code})
        for chapter in self.chapters:
            data = chapter.get_data(data)
            if data["relations"].get("Part_Chapter", None):
                data["relations"]["Part_Chapter"][Relation.INCLUDE].append({"from_id": self.id, "to_id": chapter.id})
            else:
                data["relations"]["Part_Chapter"] = {}
                data["relations"]["Part_Chapter"][Relation.INCLUDE] = [{"from_id": self.id, "to_id": chapter.id}]

        for section in self.sections:
            data = section.get_data(data)
            if data["relations"].get("Part_Section", None):
                data["relations"]["Part_Section"][Relation.INCLUDE].append({"from_id": self.id, "to_id": section.id})
            else:
                data["relations"]["Part_Section"] = {}
                data["relations"]["Part_Section"][Relation.INCLUDE] = [{"from_id": self.id, "to_id": section.id}]

        for subsection in self.subsections:
            data = subsection.get_data(data)
            if data["relations"].get("Part_SubSection", None):
                data["relations"]["Part_SubSection"][Relation.INCLUDE].append({"from_id": self.id, "to_id": subsection.id})
            else:
                data["relations"]["Part_SubSection"] = {}
                data["relations"]["Part_SubSection"][Relation.INCLUDE] = [{"from_id": self.id, "to_id": subsection.id}]

        for article in self.articles:
            data = article.get_data(data)
            if data["relations"].get("Part_Article", None):
                data["relations"]["Part_Article"][Relation.INCLUDE].append({"from_id": self.id, "to_id": article.id})
            else:
                data["relations"]["Part_Article"] = {}
                data["relations"]["Part_Article"][Relation.INCLUDE] = [{"from_id": self.id, "to_id": article.id}]
        return data

    def get_content(self):
        """Return compiled content of part over all it's chapters, sections,  subsections and articles.

        Raises:
            NotImplementedError: If called on the base class.

        Returns:
            str: The compiled content of the part based on all chapters, sections, subsections's content and article's content.
        """
        pass

    def append_chapters(self, list_chapters: Optional[List[Chapter]] = []):
        """Update chapters attribute.

        Returns:
            void: Append new update chapters.
        """
        self.chapters.extend(list_chapters)

    def append_sections(self, list_sections: Optional[List[Section]] = []):
        """Update sections attribute.

        Returns:
            void: Append new update sections.
        """
        self.sections.extend(list_sections)

    def append_subsections(self, list_subsections: Optional[List[SubSection]] = []):
        """Update subsections attribute.

        Returns:
            void: Append new update subsections.
        """
        self.subsections.extend(list_subsections)

    def append_articles(self, list_articles: Optional[List[Article]] = []):
        """Update articles attribute.

        Returns:
            void: Append new update articles.
        """
        self.articles.extend(list_articles)


class Title(NodeABC):

    def __init__(self, name: str, id: str = "", code: str = ""):
        super().__init__(name=name, id=id, code=code)
        """Initialize a Title instance.

        Args:
            name (str): The title's name.
            id (str): The title's id. Defaults to "".
            code (str): The title's code . Defaults to "".
            parts (list): The list of parts of this title.
            chapters (list): The list of chapters of this title.
        """
        self.parts = []
        self.chapters = []
    
    def structure_represent(self, tab_index: int = 1):
        tab = "\t" * tab_index 
        represent = f"{tab}TITLE\n{tab}name: {self.name} --- id: {self.id} --- code: {self.code}\n"
        for part in self.parts:
            represent += part.structure_represent(tab_index+1)
        for chapter in self.chapters:
            represent += chapter.structure_represent(tab_index+1)
        return represent
    
    def insert_neo4j(self, neo4j_client):
        neo4j_client.insert_nodes_if_not_exist("Title", [{"id": self.id, "name": self.name, "code": self.code}])
        part_ids = []
        for part in self.parts:
            part_id = part.insert_neo4j(neo4j_client)
            part_ids.append(part_id)
        neo4j_client.insert_include_batch("Title", "Part", Relation.INCLUDE, [{"from_id": self.id, "to_id": t_id} for t_id in part_ids])

        chapter_ids = []
        for chapter in self.chapters:
            chapter_id = chapter.insert_neo4j(neo4j_client)
            chapter_ids.append(chapter_id)
        neo4j_client.insert_include_batch("Title", "Chapter", Relation.INCLUDE, [{"from_id": self.id, "to_id": t_id} for t_id in chapter_ids])
        return self.id
    
    def get_data(self, data):
        data["nodes"].append({"node_type": "Title", "id": self.id, "name": self.name, "code": self.code})
        for part in self.parts:
            data = part.get_data(data)
            if data["relations"].get("Title_Part", None):
                data["relations"]["Title_Part"][Relation.INCLUDE].append({"from_id": self.id, "to_id": part.id})
            else:
                data["relations"]["Title_Part"] = {}
                data["relations"]["Title_Part"][Relation.INCLUDE] = [{"from_id": self.id, "to_id": part.id}]

        for chapter in self.chapters:
            data = chapter.get_data(data)
            if data["relations"].get("Title_Chapter", None):
                data["relations"]["Title_Chapter"][Relation.INCLUDE].append({"from_id": self.id, "to_id": chapter.id})
            else:
                data["relations"]["Title_Chapter"] = {}
                data["relations"]["Title_Chapter"][Relation.INCLUDE] = [{"from_id": self.id, "to_id": chapter.id}]
        return data

    def get_content(self):
        """Return compiled content of part over all it's parts and chapters.

        Raises:
            NotImplementedError: If called on the base class.

        Returns:
            str: The compiled content of the part based on all parts and chapters's content.
        """
        pass

    def append_parts(self, list_parts: Optional[List[Part]] = []):
        """Update parts attribute.

        Returns:
            void: Append new update parts.
        """
        self.parts.extend(list_parts)

    def append_chapters(self, list_chapters: Optional[List[Chapter]] = []):
        """Update chapters attribute.

        Returns:
            void: Append new update chapters.
        """
        self.chapters.extend(list_chapters)


class Subject(NodeABC):

    def __init__(self, name: str, id: str = "", code: str = ""):
        """Initialize a Subject instance.

        Args:
            name (str): The subject's name.
            id (str): The subject's id. Defaults to "".
            code (str): The subject's code . Defaults to "".
            titles (list): The list of titles of this title.
        """
        super().__init__(name=name, id=id, code=code)
        self.titles = []
    
    def structure_represent(self, tab_index: int=0):
        represent = f"SUBJECT\nname: {self.name} --- id: {self.id} --- code: {self.code}\n"
        for title in self.titles:
            represent += title.structure_represent(tab_index=tab_index+1)
        return represent
    
    def insert_neo4j(self, neo4j_client):
        neo4j_client.insert_nodes_if_not_exist("Subject", [{"id": self.id, "name": self.name, "code": self.code}])
        title_ids = []
        for title in self.titles:
            title_id = title.insert_neo4j(neo4j_client)
            title_ids.append(title_id)
        neo4j_client.insert_include_batch("Subject", "Title", Relation.INCLUDE, [{"from_id": self.id, "to_id": t_id} for t_id in title_ids])
        return self.id
    
    def get_data(self, data):
        data["nodes"].append({"node_type": "Subject", "id": self.id, "name": self.name, "code": self.code})
        for title in self.titles:
            data = title.get_data(data)
            if data["relations"].get("Subject_Title", None):
                data["relations"]["Subject_Title"][Relation.INCLUDE].append({"from_id": self.id, "to_id": title.id})
            else:
                data["relations"]["Subject_Title"] = {}
                data["relations"]["Subject_Title"][Relation.INCLUDE] = [{"from_id": self.id, "to_id": title.id}]
            
        return data

    def get_content(self):
        """Return compiled content of subject over all it's titles.

        Raises:
            NotImplementedError: If called on the base class.

        Returns:
            str: The compiled content of the part based on all titles's content.
        """
        pass

    def append_titles(self, list_titles: Optional[List[Title]] = []):
        """Update titles attribute.

        Returns:
            void: Append new update titles.
        """
        self.titles.extend(list_titles)
